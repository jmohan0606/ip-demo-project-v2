"use client";
import { motion, AnimatePresence } from "framer-motion";
export function GlobalLoadingOverlay({ active, message }: { active: boolean; message: string }) {
  return (
    <AnimatePresence>
      {active && (
        <motion.div className="fixed inset-0 z-50 grid place-items-center bg-background/70 backdrop-blur-xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="glass-panel w-[420px] rounded-3xl p-8 text-center">
            <div className="mx-auto h-14 w-14 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
            <h3 className="mt-5 text-lg font-black">Processing intelligence</h3>
            <p className="mt-2 text-sm text-muted-foreground">{message}</p>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
