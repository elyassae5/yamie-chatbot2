import { apiClient } from './api';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface User {
  username: string;
  email: string | null;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  email: string | null;
  role: string;
  message: string;
}

// Login function
export const login = async (credentials: LoginCredentials): Promise<User> => {
  const response = await apiClient.post<LoginResponse>('/auth/login', credentials);
  const { access_token, username, email, role } = response.data;
  
  // Store token and user info
  localStorage.setItem('auth_token', access_token);
  const user = { username, email, role };
  localStorage.setItem('user', JSON.stringify(user));
  
  return user;
};

// Logout function
export const logout = () => {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
  window.location.href = '/login';
};

// Check if user is authenticated
export const isAuthenticated = (): boolean => {
  return !!localStorage.getItem('auth_token');
};

// Get current user from localStorage
export const getCurrentUser = (): User | null => {
  const userStr = localStorage.getItem('user');
  if (!userStr) return null;
  try {
    return JSON.parse(userStr);
  } catch {
    return null;
  }
};