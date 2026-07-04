import { Card } from "@/components/ui/card";
import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="flex flex-col gap-6 h-full">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground mt-2">Configure application preferences.</p>
      </div>
      <Card className="flex-1 flex items-center justify-center border-dashed border-2 bg-transparent min-h-[400px]">
        <div className="text-center space-y-4">
          <div className="mx-auto rounded-full bg-muted p-4 w-16 h-16 flex items-center justify-center">
            <Settings className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-lg">Settings Coming Soon</h3>
          <p className="text-sm text-muted-foreground max-w-[300px]">
            API configurations, team management, and global preferences will be available here.
          </p>
        </div>
      </Card>
    </div>
  );
}
