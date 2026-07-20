"use client";

import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PersonaScopeSelector } from "@/components/status/persona-scope-selector";

export function MobileContextDrawer() {
  return (
    <div className="2xl:hidden">
      <Button variant="outline" className="gap-2">
        <SlidersHorizontal className="h-4 w-4" />
        Context
      </Button>
      <div className="sr-only">
        <PersonaScopeSelector />
      </div>
    </div>
  );
}
