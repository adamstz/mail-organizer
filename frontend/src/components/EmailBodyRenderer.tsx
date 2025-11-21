import React, { useState, useEffect } from 'react';
import { Box, Button, Typography, Link, Alert, CircularProgress } from '@mui/material';
import {
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Link as LinkIcon,
  Image as ImageIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import DOMPurify from 'isomorphic-dompurify';

interface EmailBodyRendererProps {
  messageId: string;
  defaultRichMode?: boolean;
}

interface ProcessedEmailBody {
  sanitized_html: string;
  plain_text: string;
  has_external_images: boolean;
  external_image_count: number;
  tracking_pixels_removed: number;
  has_blocked_content: boolean;
}

const EmailBodyRenderer: React.FC<EmailBodyRendererProps> = ({ 
  messageId,
  defaultRichMode = false 
}) => {
  const [showRichContent, setShowRichContent] = useState(defaultRichMode);
  const [imagesEnabled, setImagesEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emailData, setEmailData] = useState<ProcessedEmailBody | null>(null);

  // Fetch sanitized email body from new API endpoint
  useEffect(() => {
    const fetchEmailBody = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const blockImages = !imagesEnabled;
        const response = await fetch(
          `/messages/${messageId}/body?block_images=${blockImages}`
        );
        
        if (!response.ok) {
          throw new Error(`Failed to fetch email body: ${response.statusText}`);
        }
        
        const data: ProcessedEmailBody = await response.json();
        setEmailData(data);
        
        console.log(
          `[EmailBodyRenderer] Loaded email body: ` +
          `${data.tracking_pixels_removed} tracking pixels removed, ` +
          `${data.external_image_count} external images detected`
        );
      } catch (err) {
        console.error('[EmailBodyRenderer] Error fetching email body:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchEmailBody();
  }, [messageId, imagesEnabled]);

  // Function to linkify URLs in plain text (for safe mode)
  const linkifyText = (text: string): React.ReactNode[] => {
    if (!text) return [];

    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    
    // Combine URL and email patterns
    const combinedPattern = /(https?:\/\/[^\s<>'"]+?)(?=[.,;:!?)\]]*(?:\s|$))|([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/gi;
    let match;
    
    while ((match = combinedPattern.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }
      
      const matchedText = match[0];
      
      if (match[1]) {
        // It's a URL
        let displayUrl = matchedText;
        
        // Truncate very long URLs for display
        if (matchedText.length > 60) {
          try {
            const url = new URL(matchedText);
            displayUrl = `${url.protocol}//${url.hostname}/...`;
          } catch {
            displayUrl = matchedText.substring(0, 57) + '...';
          }
        }
        
        parts.push(
          <Link
            key={`url-${match.index}`}
            href={matchedText}
            target="_blank"
            rel="noopener noreferrer"
            sx={{ 
              color: 'primary.main',
              textDecoration: 'underline',
              wordBreak: 'break-word',
            }}
          >
            {displayUrl}
          </Link>
        );
      } else if (match[2]) {
        // It's an email address
        parts.push(
          <Link
            key={`email-${match.index}`}
            href={`mailto:${matchedText}`}
            sx={{ 
              color: 'primary.main',
              textDecoration: 'underline',
            }}
          >
            {matchedText}
          </Link>
        );
      }
      
      lastIndex = match.index + matchedText.length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }
    
    return parts.length > 0 ? parts : [text];
  };

  // Render safe mode (plain text with clickable links)
  const renderSafeMode = () => {
    if (!emailData) return null;

    // Don't filter out empty lines - preserve whitespace for readability
    const lines = emailData.plain_text.split('\n');
    
    // Check if we have anything security-related to show
    const hasSecurityInfo = emailData.tracking_pixels_removed > 0 || emailData.has_external_images;
    
    return (
      <Box>
        {/* Security info banner - only show if there's something to report */}
        {hasSecurityInfo && (
          <Alert 
            severity="success" 
            icon={<SecurityIcon />}
            sx={{ mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
              <Typography variant="body2">
                ✓ Safe mode
                {emailData.tracking_pixels_removed > 0 && `: ${emailData.tracking_pixels_removed} tracking pixel(s) removed (won't load even with images enabled)`}
              </Typography>
              {emailData.has_external_images && (
                <Button
                  size="small"
                  startIcon={<VisibilityIcon />}
                  onClick={() => setShowRichContent(true)}
                  variant="outlined"
                >
                  Show Rich Content
                </Button>
              )}
            </Box>
          </Alert>
        )}

        {/* Plain text content with linkified URLs */}
        <Typography 
          component="div" 
          variant="body1" 
          sx={{ 
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {lines.map((line, lineIndex) => (
            <Box key={lineIndex}>
              {line.trim().length > 0 ? linkifyText(line) : '\u00A0'}
            </Box>
          ))}
        </Typography>
      </Box>
    );
  };

  // Render rich mode (sanitized HTML with image controls)
  const renderRichMode = () => {
    if (!emailData) return null;

    // Double-sanitize on client side (defense in depth)
    // Note: Allow same tags/attributes as backend for consistency
    const sanitizedHtml = DOMPurify.sanitize(emailData.sanitized_html, {
      ALLOWED_TAGS: [
        'p', 'br', 'div', 'span', 'a', 'img', 'b', 'i', 'u', 'strong', 'em', 'mark', 'small',
        'del', 'ins', 'sub', 'sup', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
        'dl', 'dt', 'dd', 'blockquote', 'pre', 'code', 'table', 'thead', 'tbody', 'tfoot',
        'tr', 'td', 'th', 'caption', 'colgroup', 'col', 'hr', 'abbr', 'cite', 'q', 'time',
        'style', 'font', 'center', 'article', 'section', 'header', 'footer', 'nav', 'aside',
        'figure', 'figcaption', 'main', 'address', 's', 'strike', 'tt', 'kbd', 'samp', 'var',
      ],
      ALLOWED_ATTR: [
        'href', 'src', 'alt', 'title', 'target', 'rel', 'style', 'data-blocked', 'data-blocked-src',
        'class', 'id', 'dir', 'lang', 'width', 'height', 'border', 'align', 'valign', 'bgcolor',
        'background', 'cellpadding', 'cellspacing', 'colspan', 'rowspan', 'hspace', 'vspace',
        'color', 'size', 'face', 'type', 'start', 'value', 'cite', 'datetime', 'name',
      ],
      ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|cid|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    });
    
    return (
      <Box>
        {/* Image blocking warning/controls */}
        {emailData.has_external_images && (
          <Alert 
            severity={imagesEnabled ? "warning" : "info"}
            icon={<ImageIcon />}
            sx={{ mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 2 }}>
              <Box>
                {imagesEnabled ? (
                  <Typography variant="body2">
                    📷 Images loaded ({emailData.external_image_count}) - External servers can see your IP address
                  </Typography>
                ) : (
                  <Typography variant="body2">
                    📷 {emailData.external_image_count} external images blocked for privacy
                  </Typography>
                )}
                {emailData.tracking_pixels_removed > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    ✓ {emailData.tracking_pixels_removed} tracking pixel(s) removed
                  </Typography>
                )}
              </Box>
              <Box sx={{ display: 'flex', gap: 1 }}>
                {!imagesEnabled && (
                  <Button
                    size="small"
                    startIcon={<VisibilityIcon />}
                    onClick={() => setImagesEnabled(true)}
                    variant="contained"
                  >
                    Load Images
                  </Button>
                )}
                {imagesEnabled && (
                  <Button
                    size="small"
                    startIcon={<VisibilityOffIcon />}
                    onClick={() => setImagesEnabled(false)}
                    variant="outlined"
                  >
                    Block Images Again
                  </Button>
                )}
                <Button
                  size="small"
                  onClick={() => setShowRichContent(false)}
                  variant="outlined"
                >
                  Safe Mode
                </Button>
              </Box>
            </Box>
          </Alert>
        )}

        {/* Rich content mode notice */}
        {!emailData.has_external_images && (
          <Alert 
            severity="info" 
            icon={<LinkIcon />}
            sx={{ mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="body2">
                Rich content mode - HTML sanitized
              </Typography>
              <Button
                size="small"
                onClick={() => setShowRichContent(false)}
              >
                Switch to Safe Mode
              </Button>
            </Box>
          </Alert>
        )}

        {/* Sanitized HTML content */}
        <Box
          sx={{
            '& img': {
              maxWidth: '100%',
              height: 'auto',
            },
            '& a': {
              color: 'primary.main',
              textDecoration: 'underline',
            },
            wordBreak: 'break-word',
          }}
          dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
        />
      </Box>
    );
  };

  // Loading state
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load email content: {error}
      </Alert>
    );
  }

  // No data
  if (!emailData) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No email content available
      </Alert>
    );
  }

  // Decide which mode to render
  const hasHtmlContent = emailData.sanitized_html && emailData.sanitized_html.trim().length > 0;
  
  if (showRichContent && hasHtmlContent) {
    return renderRichMode();
  } else {
    return renderSafeMode();
  }
};

export default EmailBodyRenderer;
