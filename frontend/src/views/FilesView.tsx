import React, { useEffect, useState } from 'react';
import {
  Check,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode,
  Folder,
  FolderOpen,
} from 'lucide-react';
import { fetchFileContent, fetchFileTree } from '../api';
import type { FileContentResponse, FileNode, FileTreeResponse } from '../types';

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
        <div key={node.path} className="select-none">
          <div
            onClick={() => toggleDir(node.path)}
            className="flex items-center space-x-1.5 py-1 px-2 rounded hover:bg-slate-700 cursor-pointer text-slate-300 text-xs font-medium"
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
          >
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
            )}
            {isExpanded ? (
              <FolderOpen className="w-4 h-4 text-amber-400" />
            ) : (
              <Folder className="w-4 h-4 text-amber-400" />
            )}
            <span className="truncate">{node.name}</span>
          </div>

          {isExpanded && node.children && (
            <div>{node.children.map((child) => renderNode(child, depth + 1))}</div>
          )}
        </div>
      );
    }

    return (
      <div
        key={node.path}
        onClick={() => setSelectedFile(node.path)}
        className={`flex items-center space-x-1.5 py-1 px-2 rounded cursor-pointer text-xs transition ${
          isSelected
            ? 'bg-teal-600/30 text-teal-300 font-semibold border-l-2 border-teal-500'
            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700'
        }`}
        style={{ paddingLeft: `${depth * 12 + 20}px` }}
      >
        <FileCode className={`w-3.5 h-3.5 ${isSelected ? 'text-teal-400' : 'text-slate-500'}`} />
        <span className="truncate">{node.name}</span>
        <span className="ml-auto text-[10px] text-slate-500">
          {(node.size / 1024).toFixed(1)}k
        </span>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 gap-4 h-[calc(100vh-170px)]">
      {/* File Tree Left Pane */}
      <div className="md:col-span-4 lg:col-span-3 bg-slate-950 border border-slate-800 rounded-md overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Files ({tree?.total_files || 0})
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-500">Loading files...</div>
          ) : tree?.root.children ? (
            tree.root.children.map((child) => renderNode(child, 0))
          ) : (
            <div className="p-4 text-xs text-slate-500">No files indexed</div>
          )}
        </div>
      </div>

      {/* Code Viewer Right Pane */}
      <div className="md:col-span-8 lg:col-span-9 bg-slate-950 border border-slate-800 rounded-md overflow-hidden flex flex-col">
        {/* File Header */}
        <div className="px-4 py-2.5 border-b border-slate-800 bg-slate-900 flex items-center justify-between">
          <div className="flex items-center space-x-2 truncate">
            <FileCode className="w-4 h-4 text-teal-400" />
            <span className="text-xs font-mono font-medium text-slate-200 truncate">
              {content?.path || selectedFile || 'Select a file'}
            </span>
            {content && (
              <span className="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                {content.line_count} lines
              </span>
            )}
          </div>

          {content && (
            <button
              onClick={handleCopy}
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-600 text-xs font-medium text-slate-300 transition"
              title="Copy code to clipboard"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 text-slate-400" />
                  <span>Copy</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Source Code with Line Numbers */}
        <div className="flex-1 overflow-auto bg-[#0a0d14] font-mono text-xs text-slate-300 p-4 scrollbar-thin">
          {content ? (
            <div className="table w-full">
              {content.content.split('\n').map((line, idx) => (
                 <div key={idx} className="table-row hover:bg-slate-950/5">
                   <span className="table-cell select-none text-right pr-4 text-slate-400 w-12 border-r border-slate-800">
                    {idx + 1}
                  </span>
                  <span className="table-cell pl-4 whitespace-pre">
                    {line || '\n'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-slate-500 text-sm">
              Select a file from the explorer to view its source code
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
