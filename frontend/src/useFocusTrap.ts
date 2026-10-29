import { useEffect, useRef } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Keep keyboard focus inside a dialog while it's open, then hand it back to
 * whatever had focus before (usually the button that opened it).
 */
export function useFocusTrap<T extends HTMLElement>(active: boolean) {
  const ref = useRef<T>(null);
  const opener = useRef<HTMLElement | null>(null);

  // While closed, remember the last focused element. Done with a listener rather
  // than at open time, because an autoFocus input inside has already taken focus by then.
  useEffect(() => {
    if (active) return;
    opener.current = document.activeElement as HTMLElement | null;
    const onFocus = (e: FocusEvent) => {
      opener.current = e.target as HTMLElement;
    };
    document.addEventListener('focusin', onFocus);
    return () => document.removeEventListener('focusin', onFocus);
  }, [active]);

  useEffect(() => {
    const box = ref.current;
    if (!active || !box) return;
    const items = () => Array.from(box.querySelectorAll<HTMLElement>(FOCUSABLE));
    // Focus still outside means no autoFocus ran: whatever has it now opened the dialog
    const returnTo = box.contains(document.activeElement)
      ? opener.current
      : (document.activeElement as HTMLElement | null);
    if (!box.contains(document.activeElement)) (items()[0] ?? box).focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const all = items();
      if (all.length === 0) {
        e.preventDefault();
        return;
      }
      const first = all[0];
      const last = all[all.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      returnTo?.focus();
    };
  }, [active]);

  return ref;
}
