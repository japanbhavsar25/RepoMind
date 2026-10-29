import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronRight, Copy } from 'lucide-react';
import { fetchFileContent, fetchFileTree } from '../api';
import type { FileContentResponse, FileNode, FileTreeResponse } from '../types';
import { Button, Notice } from '../components/ui';

interface FilesViewProps {
  repoId: string;
  initialPath?: string;
  /** A line to scroll to and highlight, e.g. the start of a citation */
  initialLine?: number;
}

function findFirstFile(node: FileNode): FileNode | null {
  if (node.type === 'file') return node;
  for (const child of node.children ?? []) {
    const res = findFirstFile(child);
    if (res) return res;
  }
  return null;
}

function allFiles(node: FileNode): string[] {
  return node.type === 'file' ? [node.path] : (node.children ?? []).flatMap(allFiles);
}

/** Match a path as written in an answer (often just `auth.py`) to a real file in the tree. */
function resolvePath(root: FileNode, wanted: string): string {
  const files = allFiles(root);
  if (!wanted || files.includes(wanted)) return wanted;
  const matches = files.filter((f) => f.endsWith(`/${wanted}`));
  return matches.length === 1 ? matches[0] : wanted;
}

export const FilesView: React.FC<FilesViewProps> = ({ repoId, initialPath, initialLine }) => {
  const [tree, setTree] = useState<FileTreeResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>(initialPath || '');
  const [content, setContent] = useState<FileContentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [contentError, setContentError] = useState<string | null>(null);
  const highlightRef = useRef<HTMLTableRowElement>(null);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['root']));

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchFileTree(repoId)
      .then((data) => {
        if (!isMounted) return;
        setTree(data);
        // Resolve a short path to the real file, or default to the first file
        setSelectedFile((prev) => (prev ? resolvePath(data.root, prev) : findFirstFile(data.root)?.path ?? ''));
      })
      .catch((err) => console.error('Failed to load file tree:', err))
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [repoId]);

  useEffect(() => {
    // Wait for the tree, so a short path is resolved before it's fetched
    if (!selectedFile || !tree) return;
    let isMounted = true;
    fetchFileContent(selectedFile, repoId)
      .then((data) => {
        if (!isMounted) return;
        setContent(data);
        setContentError(null);
      })
      .catch((err) => {
        if (!isMounted) return;
        setContent(null);
        setContentError(err instanceof Error ? err.message : `Couldn't open ${selectedFile}.`);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedFile, repoId, tree]);

  // Bring the cited line into view once the file is showing
  useEffect(() => {
    highlightRef.current?.scrollIntoView({ block: 'center' });
  }, [content]);

  // Open the folders leading to the selected file so it's visible in the tree
  useEffect(() => {
    if (!selectedFile) return;
    const parts = selectedFile.split('/').slice(0, -1);
    if (parts.length === 0) return;
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      parts.forEach((_, i) => next.add(parts.slice(0, i + 1).join('/')));
      return next;
    });
  }, [selectedFile]);

  const toggleDir = (path: string) => {
    setExpandedDirs((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const renderNode = (node: FileNode, depth = 0) => {
    const isDir = node.type === 'directory';
    const isExpanded = expandedDirs.has(node.path);
    const isSelected = selectedFile === node.path;

    if (isDir) {
      return (
        <div key={node.path}>
          <button
            onClick={() => toggleDir(node.path)}
            aria-expanded={isExpanded}
            className="w-full flex items-center gap-1 py-1 pr-2 rounded text-left text-[13px] text-ink hover:bg-sunk"
            style={{ paddingLeft: `${depth * 14 + 6}px` }}
          >
            <ChevronRight className={`w-3.5 h-3.5 text-subtle transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
            <span className="truncate font-medium">{node.name}/</span>
          </button>
          {isExpanded && node.children && <div>{node.children.map((child) => renderNode(child, depth + 1))}</div>}
        </div>
      );
    }

    return (
      <button
        key={node.path}
        onClick={() => setSelectedFile(node.path)}
        aria-current={isSelected ? 'true' : undefined}
        className={`w-full flex items-center gap-2 py-1 pr-2 rounded text-left text-[13px] transition ${
          isSelected ? 'bg-accent-soft text-accent font-medium' : 'text-muted hover:text-ink hover:bg-sunk'
        }`}
        style={{ paddingLeft: `${depth * 14 + 25}px` }}
      >
        <span className="truncate">{node.name}</span>
        <span className="ml-auto text-[11px] text-subtle tabular-nums">{(node.size / 1024).toFixed(1)}k</span>
      </button>
    );
  };

  const lines = content ? content.content.split('\n') : [];
  // Highlight only in the file that was opened from a citation or result
  const openedPath = tree && initialPath ? resolvePath(tree.root, initialPath) : undefined;
  const highlightLine = content && content.path === openedPath ? initialLine : undefined;

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 md:h-[calc(100vh-200px)] md:min-h-[480px]">
      <aside className="md:col-span-4 lg:col-span-3 flex flex-col min-h-0 max-h-72 md:max-h-none">
        <p className="text-xs text-subtle mb-2 px-1">
          {tree ? `${tree.total_files} Python files` : 'Files'}
        </p>
        <div className="flex-1 overflow-y-auto pr-1">
          {loading ? (
            <p className="p-2 text-sm text-muted">Loading files…</p>
          ) : tree?.root.children ? (
            tree.root.children.map((child) => renderNode(child, 0))
          ) : (
            <p className="p-2 text-sm text-muted">No files have been indexed yet.</p>
          )}
        </div>
      </aside>

      <section className="md:col-span-8 lg:col-span-9 bg-surface border border-line rounded-lg overflow-hidden flex flex-col min-h-[420px]">
        <div className="px-4 py-2.5 border-b border-line flex items-center justify-between gap-3">
          <div className="flex items-baseline gap-2 min-w-0">
            <span className="text-sm font-mono text-ink truncate">{content?.path || selectedFile || 'No file selected'}</span>
            {content && <span className="text-xs text-subtle shrink-0">{content.line_count} lines</span>}
          </div>
          {content && (
            <Button size="sm" variant="quiet" onClick={handleCopy} title="Copy the file's contents">
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-good" /> Copied
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" /> Copy
                </>
              )}
            </Button>
          )}
        </div>

        <div className="flex-1 overflow-auto bg-sunk/50 font-mono text-[12.5px] leading-relaxed text-ink py-3">
          {content ? (
            <table className="w-full border-collapse">
              <tbody>
                {lines.map((line, idx) => (
                  <tr
                    key={idx}
                    ref={idx + 1 === highlightLine ? highlightRef : undefined}
                    className={idx + 1 === highlightLine ? 'bg-accent-soft' : 'hover:bg-accent-soft/40'}
                  >
                    <td className="select-none text-right pr-4 pl-4 text-subtle w-12 align-top tabular-nums">
                      {idx + 1}
                    </td>
                    <td className="pr-4 whitespace-pre">{line || ' '}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : contentError ? (
            <div className="px-4 font-sans">
              <Notice tone="error">{contentError}</Notice>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-sm text-muted font-sans">
              Pick a file on the left to read it here.
            </div>
          )}
        </div>
      </section>
    </div>
  );
};
