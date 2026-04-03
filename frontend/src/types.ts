export type UserRole = 'pending' | 'employee' | 'manager';

export interface User {
  id: number;
  name: string;
  role: UserRole;
  telegram_user_id: string;
  telegram_username?: string;
}

export interface Task {
  id: number;
  title: string;
  description?: string;
  start_at: string;
  end_at: string;
  required_people: number;
  created_by: number;
  team_id?: number | null;
  assigned_people: number;
  missing_people: number;
  is_fully_staffed: boolean;
  assigned_users: TaskAssignee[];
}

export interface TaskAssignee {
  id: number;
  name: string;
  role: UserRole;
}

export interface ConflictItem {
  task_id: number;
  title: string;
  start_at: string;
  end_at: string;
}

export interface AssignmentOut {
  id: number;
  task_id: number;
  assignee_id: number;
  conflicts: ConflictItem[];
}

export interface DayScheduleResponse {
  user_id: number;
  date: string;
  tasks: Task[];
}

export interface ConflictResponse {
  user_id: number;
  date: string;
  conflicts: ConflictItem[];
}

export interface UnfilledTasksResponse {
  date: string;
  tasks: Task[];
}

export interface Assignment {
  id: number;
  task_id: number;
  assignee_id: number;
}

export interface Team {
  id: number;
  name: string;
  created_by?: number | null;
  manager_id?: number | null;
}

export interface TeamMember {
  id: number;
  name: string;
  role: UserRole;
}

export interface TeamDetail extends Team {
  members: TeamMember[];
  manager?: TeamMember | null;
}

export interface TeamDetail extends Team {
  members: TeamMember[];
}
