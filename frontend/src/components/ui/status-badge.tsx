import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusType = "connected" | "disconnected" | "syncing" | "offline" | "error" | "active" | "paused" | "archived" | "deleted" | "unknown";

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const statusConfig: Record<StatusType, { label: string; dot: string; bg: string; text: string }> = {
    connected: { label: "Connected", dot: "bg-emerald-500", bg: "bg-emerald-500/10", text: "text-emerald-500" },
    active: { label: "Active", dot: "bg-emerald-500", bg: "bg-emerald-500/10", text: "text-emerald-500" },
    syncing: { label: "Syncing", dot: "bg-blue-500 animate-pulse", bg: "bg-blue-500/10", text: "text-blue-500" },
    disconnected: { label: "Disconnected", dot: "bg-yellow-500", bg: "bg-yellow-500/10", text: "text-yellow-500" },
    paused: { label: "Paused", dot: "bg-yellow-500", bg: "bg-yellow-500/10", text: "text-yellow-500" },
    archived: { label: "Archived", dot: "bg-muted-foreground", bg: "bg-muted", text: "text-muted-foreground" },
    deleted: { label: "Deleted", dot: "bg-destructive", bg: "bg-destructive/10", text: "text-destructive" },
    offline: { label: "Offline", dot: "bg-muted-foreground", bg: "bg-muted", text: "text-muted-foreground" },
    error: { label: "Error", dot: "bg-destructive", bg: "bg-destructive/10", text: "text-destructive" },
    unknown: { label: "Unknown", dot: "bg-muted-foreground", bg: "bg-muted", text: "text-muted-foreground" },
  };

  const config = statusConfig[status] || statusConfig.unknown;

  return (
    <Badge variant="outline" className={cn("gap-1.5 font-medium border-transparent", config.bg, config.text, className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </Badge>
  );
}
