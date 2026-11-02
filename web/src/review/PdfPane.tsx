import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { api, type Box } from "../api";

// Must live in the same module that renders <Document> (react-pdf README).
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const MAX_PAGE_WIDTH = 820;
const SIDE_GUTTER = 0; // contentRect already excludes the pane padding
const BOX_PAD = 3;

interface Props {
  docId: string;
  pageSizes: [number, number][];
  boxes: Box[];
  selectionKey: string;
  scrollEl: HTMLDivElement | null;
  onScrollEl: (el: HTMLDivElement | null) => void;
  onHighlight: (el: HTMLElement | null) => void;
}

function usePageWidth(el: HTMLDivElement | null): number {
  const [width, setWidth] = useState(MAX_PAGE_WIDTH);
  useEffect(() => {
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setWidth(Math.min(MAX_PAGE_WIDTH, entry.contentRect.width - SIDE_GUTTER)),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [el]);
  return Math.max(width, 320);
}

export function PdfPane({ docId, pageSizes, boxes, selectionKey, scrollEl, onScrollEl, onHighlight }: Props) {
  const width = usePageWidth(scrollEl);
  const reduced = useReducedMotion();
  const firstBox = useRef<HTMLDivElement | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    onHighlight(firstBox.current);
    firstBox.current?.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
  }, [selectionKey, width, reduced, onHighlight, isLoaded]);

  return (
    <div ref={onScrollEl} className="h-full overflow-y-auto px-8 py-6" aria-label="Document">
      <Document
        file={api.pdfUrl(docId)}
        suspense={false}
        onLoadSuccess={() => setIsLoaded(true)}
        loading={<p className="text-meta text-ink-muted">Loading the PDF</p>}
        error={<p className="text-meta text-reject">Could not load this PDF. Check that the API is running.</p>}
      >
        {pageSizes.map(([pageWidth, pageHeight], index) => {
          const scale = width / pageWidth;
          const pageBoxes = boxes.filter((b) => b.page === index);
          return (
            <div
              key={index}
              className="relative mx-auto mb-6 border border-rule bg-surface"
              style={{ width, height: pageHeight * scale }}
            >
              <Page
                pageNumber={index + 1}
                width={width}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
              {pageBoxes.map((box, n) => (
                <motion.div
                  key={`${selectionKey}-${n}`}
                  ref={index === boxes[0]?.page && n === 0 ? firstBox : undefined}
                  className="pointer-events-none absolute rounded-sm"
                  style={{
                    left: box.x0 * scale - BOX_PAD,
                    top: box.top * scale - BOX_PAD,
                    width: (box.x1 - box.x0) * scale + 2 * BOX_PAD,
                    height: (box.bottom - box.top) * scale + 2 * BOX_PAD,
                    background: "rgba(127, 157, 191, 0.32)",
                    boxShadow: "inset 0 -2px 0 var(--color-ledger-deep)",
                  }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: reduced ? 0 : 0.25 }}
                />
              ))}
            </div>
          );
        })}
      </Document>
    </div>
  );
}
