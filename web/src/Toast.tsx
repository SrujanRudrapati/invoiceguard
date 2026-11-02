import { AnimatePresence, motion } from "framer-motion";

export type ToastMessage = { id: number; text: string; tone: "info" | "error" };

export function Toast({ message }: { message: ToastMessage | null }) {
  return (
    <div className="pointer-events-none fixed bottom-20 left-1/2 z-30 -translate-x-1/2" role="status" aria-live="polite">
      <AnimatePresence mode="wait">
        {message && (
          <motion.p
            key={message.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={`rounded px-4 py-2 text-body text-white ${
              message.tone === "error" ? "bg-reject" : "bg-ink"
            }`}
          >
            {message.text}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}
