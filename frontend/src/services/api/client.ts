// API Client to interact with FastAPI and LocalStorage Mock DB

export interface BrowserProfile {
  id: string;
  name: string;
  profileId: string;
  apiUrl?: string; // Optional custom API URL for distributed RDP setups
  description?: string;
  createdAt: number;
}

export interface AdAccount {
  id: string;
  nickname: string;
  accountId: string;
  browserId: string;
  description?: string;
  createdAt: number;
}

const FASTAPI_URL = "http://127.0.0.1:8000";

const INITIAL_DB = {
  browsers: [
    { id: "b1", name: "Australia Browser", profileId: "k1dvlyr0", createdAt: Date.now() }
  ],
  accounts: [
    { id: "a1", nickname: "Australia Store", accountId: "1559140139101704", browserId: "b1", createdAt: Date.now() },
    { id: "a2", nickname: "Secondary Store", accountId: "2489049668183097", browserId: "b1", createdAt: Date.now() }
  ]
};

// Mock Database in LocalStorage
const getDb = () => {
  if (typeof window === "undefined") return INITIAL_DB;
  const data = localStorage.getItem("meta_ads_db");
  if (data) return JSON.parse(data);
  // Seed with initial data
  localStorage.setItem("meta_ads_db", JSON.stringify(INITIAL_DB));
  return INITIAL_DB;
};

const saveDb = (data: { browsers: BrowserProfile[]; accounts: AdAccount[] }) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("meta_ads_db", JSON.stringify(data));
  }
};

// Helper to resolve the correct API URL for a request
const resolveApiUrl = (profileId: string | null): string => {
  if (typeof window === "undefined") return process.env.NEXT_PUBLIC_FASTAPI_URL || "http://127.0.0.1:8000";
  
  // If we have a profile ID, try to find its custom API URL
  if (profileId) {
    const db = getDb();
    const browser = db.browsers.find((b: BrowserProfile) => b.profileId === profileId);
    if (browser && browser.apiUrl) {
      return browser.apiUrl.replace(/\/$/, ""); // Strip trailing slash
    }
  }
  
  // Fallback to environment variable or localhost
  return process.env.NEXT_PUBLIC_FASTAPI_URL || "http://127.0.0.1:8000";
};

// --- BROWSER API ---

export const getBrowsers = async (): Promise<BrowserProfile[]> => {
  // Simulate network delay
  await new Promise((r) => setTimeout(r, 300));
  return getDb().browsers;
};

export const createBrowser = async (data: Omit<BrowserProfile, "id" | "createdAt">): Promise<BrowserProfile> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  if (db.browsers.find((b: BrowserProfile) => b.profileId === data.profileId)) {
    throw new Error("Browser Profile ID already exists.");
  }
  const newBrowser: BrowserProfile = {
    ...data,
    id: crypto.randomUUID(),
    createdAt: Date.now(),
  };
  db.browsers.push(newBrowser);
  saveDb(db);
  return newBrowser;
};

export const updateBrowser = async (id: string, data: Partial<BrowserProfile>): Promise<BrowserProfile> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  const index = db.browsers.findIndex((b: BrowserProfile) => b.id === id);
  if (index === -1) throw new Error("Browser not found");
  
  if (data.profileId && db.browsers.find((b: BrowserProfile) => b.profileId === data.profileId && b.id !== id)) {
    throw new Error("Browser Profile ID already exists.");
  }

  db.browsers[index] = { ...db.browsers[index], ...data };
  saveDb(db);
  return db.browsers[index];
};

export const deleteBrowser = async (id: string): Promise<void> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  db.browsers = db.browsers.filter((b: BrowserProfile) => b.id !== id);
  // Also delete associated accounts
  db.accounts = db.accounts.filter((a: AdAccount) => a.browserId !== id);
  saveDb(db);
};

export const checkBrowserStatus = async (profileId: string) => {
  try {
    const baseUrl = resolveApiUrl(profileId);
    const res = await fetch(`${baseUrl}/health`, {
      headers: {
        "X-AdsPower-Profile-Id": profileId,
      },
    });
    if (!res.ok) throw new Error("Status check failed");
    return await res.json();
  } catch {
    throw new Error("Failed to connect to browser");
  }
};

// --- ACCOUNTS API ---

export const getAccounts = async (): Promise<AdAccount[]> => {
  await new Promise((r) => setTimeout(r, 300));
  return getDb().accounts;
};

export const createAccount = async (data: Omit<AdAccount, "id" | "createdAt">): Promise<AdAccount> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  if (db.accounts.find((a: AdAccount) => a.accountId === data.accountId)) {
    throw new Error("Ad Account ID already exists.");
  }
  const newAccount: AdAccount = {
    ...data,
    id: crypto.randomUUID(),
    createdAt: Date.now(),
  };
  db.accounts.push(newAccount);
  saveDb(db);
  return newAccount;
};

export const updateAccount = async (id: string, data: Partial<AdAccount>): Promise<AdAccount> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  const index = db.accounts.findIndex((a: AdAccount) => a.id === id);
  if (index === -1) throw new Error("Account not found");

  if (data.accountId && db.accounts.find((a: AdAccount) => a.accountId === data.accountId && a.id !== id)) {
    throw new Error("Ad Account ID already exists.");
  }

  db.accounts[index] = { ...db.accounts[index], ...data };
  saveDb(db);
  return db.accounts[index];
};

export const deleteAccount = async (id: string): Promise<void> => {
  await new Promise((r) => setTimeout(r, 400));
  const db = getDb();
  db.accounts = db.accounts.filter((a: AdAccount) => a.id !== id);
  saveDb(db);
};

export const checkAccountStatus = async (profileId: string, accountId: string) => {
  try {
    const baseUrl = resolveApiUrl(profileId);
    const res = await fetch(`${baseUrl}/account?_account=${accountId}&_t=${Date.now()}`, {
      cache: "no-store",
      headers: {
        "X-AdsPower-Profile-Id": profileId,
        "X-Ad-Account-Id": accountId,
      },
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error("Session Expired");
      if (res.status === 503) throw new Error("Browser Closed");
      throw new Error("Status check failed");
    }
    return await res.json();
  } catch (error) {
    throw new Error((error as Error).message || "Failed to connect to account");
  }
};

// --- REPORT API ---

export const getAccountReport = async (profileId: string, accountId: string, datePreset: string = "last_30d") => {
  try {
    const baseUrl = resolveApiUrl(profileId);
    const res = await fetch(`${baseUrl}/report?date_preset=${datePreset}&_account=${accountId}&_t=${Date.now()}`, {
      cache: "no-store",
      headers: {
        "X-AdsPower-Profile-Id": profileId,
        "X-Ad-Account-Id": accountId,
      },
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error("Session Expired");
      if (res.status === 503) throw new Error("Browser Closed");
      throw new Error("Report fetch failed");
    }
    return await res.json();
  } catch (error) {
    throw new Error((error as Error).message || "Failed to fetch report");
  }
};

// --- CAMPAIGNS API ---

export const getCampaigns = async (profileId: string, accountId: string, datePreset: string = "last_30d") => {
  try {
    const baseUrl = resolveApiUrl(profileId);
    const res = await fetch(`${baseUrl}/campaigns?date_preset=${datePreset}&_account=${accountId}&_t=${Date.now()}`, {
      cache: "no-store",
      headers: {
        "X-AdsPower-Profile-Id": profileId,
        "X-Ad-Account-Id": accountId,
      },
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error("Session Expired");
      if (res.status === 503) throw new Error("Browser Closed");
      throw new Error("Campaigns fetch failed");
    }
    return await res.json();
  } catch (error) {
    throw new Error((error as Error).message || "Failed to fetch campaigns");
  }
};

export const updateCampaignStatus = async (profileId: string, accountId: string, campaignId: string, status: "ACTIVE" | "PAUSED") => {
  try {
    const baseUrl = resolveApiUrl(profileId);
    const res = await fetch(`${baseUrl}/campaign/${campaignId}/status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-AdsPower-Profile-Id": profileId,
        "X-Ad-Account-Id": accountId,
      },
      body: JSON.stringify({ status }),
    });
    if (!res.ok) {
      if (res.status === 401) throw new Error("Session Expired");
      if (res.status === 503) throw new Error("Browser Closed");
      throw new Error("Failed to update campaign status");
    }
    return await res.json();
  } catch (error) {
    throw new Error((error as Error).message || "Failed to update campaign status");
  }
};
