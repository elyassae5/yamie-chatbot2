import { apiClient } from '@/lib/api';

export interface WhitelistEntry {
  id: string;
  phone_number: string;
  name: string;
  department: string;
  added_at: string;
  is_active: boolean;
  notes: string | null;
}

export interface CreateWhitelistEntry {
  phone_number: string;
  name: string;
  department: string;
  notes?: string;
}

export interface UpdateWhitelistEntry {
  is_active?: boolean;
  notes?: string;
}

// Get all whitelist entries
export const getWhitelist = async (): Promise<WhitelistEntry[]> => {
  const response = await apiClient.get<WhitelistEntry[]>('/whitelist/');
  return response.data;
};

// Add new entry
export const addWhitelistEntry = async (data: CreateWhitelistEntry): Promise<WhitelistEntry> => {
  const response = await apiClient.post<WhitelistEntry>('/whitelist/', data);
  return response.data;
};

// Update entry
export const updateWhitelistEntry = async (
  entryId: string,
  data: UpdateWhitelistEntry
): Promise<WhitelistEntry> => {
  const response = await apiClient.patch<WhitelistEntry>(`/whitelist/${entryId}`, data);
  return response.data;
};

// Delete entry
export const deleteWhitelistEntry = async (entryId: string): Promise<void> => {
  await apiClient.delete(`/whitelist/${entryId}`);
};