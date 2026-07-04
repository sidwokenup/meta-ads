"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/store/ui-store";
import {
  LayoutDashboard,
  Users,
  Building2,
  Megaphone,
  BarChart3,
  BellRing,
  Settings,
  Menu,
  ChevronLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const navItems = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Profiles", href: "/profiles", icon: Users },
  { name: "Ad Accounts", href: "/accounts", icon: Building2 },
  { name: "Campaigns", href: "/campaigns", icon: Megaphone },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Alerts", href: "/alerts", icon: BellRing },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <div
      className={cn(
        "flex flex-col border-r bg-background transition-all duration-300",
        sidebarOpen ? "w-64" : "w-16"
      )}
    >
      <div className="flex h-14 items-center justify-between border-b px-4">
        {sidebarOpen && (
          <span className="text-sm font-semibold tracking-tight">Meta Ads Reporter</span>
        )}
        <Button variant="ghost" size="icon" onClick={toggleSidebar} className="shrink-0">
          {sidebarOpen ? <ChevronLeft className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
                !sidebarOpen && "justify-center px-0"
              )}
              title={!sidebarOpen ? item.name : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span>{item.name}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="border-t p-4">
        {sidebarOpen ? (
          <div className="flex flex-col space-y-1">
            <span className="text-xs font-medium text-muted-foreground">Status</span>
            <div className="flex items-center space-x-2">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500"></span>
              <span className="text-xs text-foreground">Collector Online</span>
            </div>
          </div>
        ) : (
          <div className="flex justify-center">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500" title="Collector Online"></span>
          </div>
        )}
      </div>
    </div>
  );
}
