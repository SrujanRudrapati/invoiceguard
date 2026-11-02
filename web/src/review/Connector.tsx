import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";

interface Props {
  from: HTMLElement | null; // selected field row
  to: HTMLElement | null; // evidence highlight on the PDF
  scrollRoots: (HTMLElement | null)[]; // [pdf pane, fields panel]
  animationKey: string;
}

const MIN_VISIBLE_PX = 8;

/** True when the element's vertical middle sits inside the pane's visible box. */
function isShown(el: DOMRect, pane: DOMRect | undefined): boolean {
  if (!pane) return true;
  const middle = el.top + el.height / 2;
  return middle >= pane.top + MIN_VISIBLE_PX && middle <= pane.bottom - MIN_VISIBLE_PX;
}

/** Thin ledger-blue line from the selected field to its quote on the page. */
export function Connector({ from, to, scrollRoots, animationKey }: Props) {
  const reduced = useReducedMotion();
  const [path, setPath] = useState<{ d: string; end: [number, number] } | null>(null);

  const measure = useCallback(() => {
    if (!from || !to || !to.isConnected || !from.isConnected) return setPath(null);
    const f = from.getBoundingClientRect();
    const t = to.getBoundingClientRect();
    const [pdfPane, fieldsPane] = scrollRoots.map((r) => r?.getBoundingClientRect());
    // Never point at something the clerk can't see: a quote scrolled out of the PDF pane,
    // or a field row clipped by the panel (e.g. sitting behind the bottom bar).
    if (f.height === 0 || !isShown(t, pdfPane) || !isShown(f, fieldsPane)) return setPath(null);
    const start: [number, number] = [f.left, f.top + f.height / 2];
    const end: [number, number] = [t.right + 2, t.top + t.height / 2];
    const bend = Math.max(32, (start[0] - end[0]) / 2);
    const d = `M ${start[0]} ${start[1]} C ${start[0] - bend} ${start[1]}, ${end[0] + bend} ${end[1]}, ${end[0]} ${end[1]}`;
    setPath((prev) => (prev?.d === d ? prev : { d, end }));
  }, [from, to, scrollRoots]);

  useLayoutEffect(measure, [measure, animationKey]);

  useEffect(() => {
    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    const roots = scrollRoots.filter((r): r is HTMLElement => r !== null);
    const resizes = new ResizeObserver(schedule); // pane size changes without a window resize
    roots.forEach((r) => {
      r.addEventListener("scroll", schedule, { passive: true });
      resizes.observe(r);
    });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      resizes.disconnect();
      roots.forEach((r) => r.removeEventListener("scroll", schedule));
      window.removeEventListener("resize", schedule);
    };
  }, [measure, scrollRoots]);

  if (!path) return null;
  return (
    <svg className="pointer-events-none fixed inset-0 z-20 h-full w-full" aria-hidden="true">
      <motion.path
        key={animationKey}
        d={path.d}
        fill="none"
        stroke="var(--color-ledger)"
        strokeWidth={1.5}
        initial={{ pathLength: reduced ? 1 : 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: reduced ? 0 : 0.25, ease: "easeOut" }}
      />
      <circle cx={path.end[0]} cy={path.end[1]} r={3} fill="var(--color-ledger-deep)" />
    </svg>
  );
}
