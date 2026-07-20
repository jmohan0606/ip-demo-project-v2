import { ArrowDownRight, ArrowUpRight, LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
export function KpiCard({ label, value, change, icon: Icon, variant = "default" }: { label: string; value: string; change: string; icon: LucideIcon; variant?: "default" | "insight" | "risk"; }) {
  const positive = !change.startsWith("-");
  return (
    <Card className={cn("overflow-hidden", variant === "insight" && "insight-gradient", variant === "risk" && "risk-gradient", variant === "default" && "kpi-gradient")}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div><p className="text-sm font-semibold text-muted-foreground">{label}</p><div className="mt-2 text-3xl font-black tracking-tight">{value}</div></div>
          <div className="rounded-2xl bg-white/15 p-3"><Icon className="h-5 w-5" /></div>
        </div>
        <Badge variant={positive ? "success" : "destructive"} className="mt-4 gap-1">{positive ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />}{change}</Badge>
      </CardContent>
    </Card>
  );
}
