export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'admin' | 'agent' | 'owner';
}

export interface Ticket {
  id: string;
  subject: string;
  status: 'open' | 'pending' | 'closed' | 'spam';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assignee?: User;
  channel: ChannelType;
  createdAt: Date;
  updatedAt: Date;
  lastMessageAt?: Date;
  tags: string[];
  customer: Customer;
}

export interface Customer {
  id: string;
  firstName: string;
  lastName: string;
  email?: string;
  phone?: string;
  avatar?: string;
  channels: ChannelType[];
  tags: string[];
  notes?: string;
  customFields: Record<string, any>;
}

export type ChannelType = 
  | 'website'
  | 'facebook'
  | 'instagram'
  | 'whatsapp'
  | 'line'
  | 'shopee'
  | 'lazada'
  | 'tiktok'
  | 'gmail'
  | 'outlook'
  | 'shopify'
  | 'hubspot';

export interface ChannelConfig {
  id: string;
  type: ChannelType;
  name: string;
  connected: boolean;
  accountName?: string;
  setupGuideUrl: string;
  connectUrl: string;
  icon: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  type: 'prebuilt' | 'custom';
  triggers: Trigger[];
  actions: Action[];
  createdBy: User;
  updatedAt: Date;
}

export interface Trigger {
  type: 'message_received' | 'keyword_match' | 'time_based' | 'status_change';
  conditions: Condition[];
}

export interface Condition {
  field: string;
  operator: 'equals' | 'contains' | 'starts_with' | 'ends_with' | 'greater_than' | 'less_than';
  value: any;
}

export interface Action {
  type: 'assign_agent' | 'send_message' | 'add_tag' | 'change_status' | 'trigger_ai';
  params: Record<string, any>;
}

export interface Broadcast {
  id: string;
  name: string;
  channel: 'line' | 'whatsapp';
  status: 'draft' | 'scheduled' | 'sending' | 'completed' | 'failed';
  recipients: number;
  opened: number;
  clicked: number;
  scheduledAt?: Date;
  sentAt?: Date;
  content: BroadcastContent;
}

export interface BroadcastContent {
  text: string;
  imageUrl?: string;
  buttons?: Button[];
}

export interface Button {
  label: string;
  action: 'url' | 'reply' | 'postback';
  value: string;
}

export interface Analytics {
  tickets: TicketMetrics;
  responseTime: ResponseTimeMetrics;
  agentPerformance: AgentMetrics[];
  channelDistribution: ChannelMetrics[];
  satisfaction: SatisfactionMetrics;
}

export interface TicketMetrics {
  totalOpen: number;
  assigned: number;
  unassigned: number;
  unanswered: number;
  waitingOver10Min: number;
  closedToday: number;
  createdToday: number;
}

export interface ResponseTimeMetrics {
  averageFirstResponse: string;
  averageResolutionTime: string;
  withinSLA: number;
  breachedSLA: number;
}

export interface AgentMetrics {
  agentId: string;
  agentName: string;
  ticketsResolved: number;
  averageResponseTime: string;
  satisfactionScore: number;
}

export interface ChannelMetrics {
  channel: ChannelType;
  count: number;
  percentage: number;
}

export interface SatisfactionMetrics {
  totalResponses: number;
  averageScore: number;
  distribution: {
    5: number;
    4: number;
    3: number;
    2: number;
    1: number;
  };
}

export interface AIBotConfig {
  enabled: boolean;
  personality: string;
  knowledgeBaseSize: number;
  maxKnowledgeBaseSize: number;
  trainingSources: TrainingSource[];
  handoverRules: HandoverRule[];
}

export interface TrainingSource {
  id: string;
  name: string;
  type: 'url' | 'faq' | 'document' | 'policy';
  status: 'processing' | 'completed' | 'failed';
  characterCount: number;
  uploadedBy: User;
  updatedAt: Date;
}

export interface HandoverRule {
  id: string;
  condition: string;
  action: 'assign_to_agent' | 'escalate' | 'create_ticket';
  targetId?: string;
}

export interface BusinessSettings {
  organizationName: string;
  email: string;
  phone: string;
  storeId: string;
  timezone: string;
  logo?: string;
  businessHours: BusinessHour[];
}

export interface BusinessHour {
  day: number; // 0 = Sunday, 6 = Saturday
  open: string; // HH:mm format
  close: string; // HH:mm format
  isClosed: boolean;
}

export interface TrialInfo {
  isActive: boolean;
  daysRemaining: number;
  expiryDate: Date;
  upgradeUrl: string;
}
