import React, { useEffect, useState } from 'react';
import { Check, ChevronRight, Copy } from 'lucide-react';
import { fetchFileContent, fetchFileTree } from '../api';
import type { FileContentResponse, FileNode, FileTreeResponse } from '../types';
import { Button } from '../components/ui';

interface FilesViewProps {
  repoId: string;
  initialPath?: string;
}

export const FilesView: React.FC<FilesViewProps> = ({ repoId, initialPath }) => {
  const [tree, setTree] = useState<FileTreeResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>(initialPath || '');
  const [content, setContent] = useState<FileContentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['root']));

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    fetchFileTree(repoId)
      .then((data) => {
        if (!isMounted) return;
        setTree(data);
        // Default select first file if none selected
        if (!selectedFile && data.root.children) {
          const firstFile = findFirstFile(data.root);
          if (firstFile) setSelectedFile(firstFile.path);
        }
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
    if (!selectedFile) return;
    let isMounted = true;
    fetchFileContent(selectedFile, repoId)
      .then((data) => {
        if (isMounted) setContent(data);
      })
      .catch((err) => console.error('Failed to load file content:', err));

    return () => {
      isMounted = false;
    };
  }, [selectedFile, repoId]);

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

  const findFirstFile = (node: FileNode): FileNode | null => {
    if (node.type === 'file') return node;
    if (node.children) {
      for (const child of node.children) {
        const res = findFirstFile(child);
        if (res) return res;
      }
    }
    return null;
  };

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
                  <tr key={idx} className="hover:bg-accent-soft/40">
                    <td className="select-none text-right pr-4 pl-4 text-subtle w-12 align-top tabular-nums">
                      {idx + 1}
                    </td>
                    <td className="pr-4 whitespace-pre">{line || ' '}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
