export interface Email {
  id: number;
  subject: string;
  date: string;
  priority: 'High' | 'Medium' | 'Low' | 'Unclassified';
  summary: string;
  body: string;
  classificationLabels?: string[];
  isClassified: boolean;
  _raw?: {
    from?: unknown;
    to?: unknown;
  };
}