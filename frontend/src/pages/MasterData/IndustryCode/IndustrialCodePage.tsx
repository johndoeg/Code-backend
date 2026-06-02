import React, { useState, useEffect, useCallback } from 'react';

interface IndustryNode {
    code: string;
    parent: string;
    kepala: string;
    descrip: string;
    children: IndustryNode[];
}

interface IndustrialCodePageProps {
    onSelect?: (node: IndustryNode) => void;
}

const ChevronRight = ({ open }: { open: boolean }) => (
    <svg
        viewBox="0 0 16 16"
        width="14"
        height="14"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
            transition: 'transform 200ms ease',
            transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
            flexShrink: 0,
        }}
    >
        <polyline points="6 4 10 8 6 12" />
    </svg>
);

const DotIcon = () => (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" style={{ flexShrink: 0 }}>
        <circle cx="8" cy="8" r="2.5" />
    </svg>
);

const SearchIcon = () => (
    <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="9" cy="9" r="6" />
        <line x1="14" y1="14" x2="18" y2="18" />
    </svg>
);

const RefreshIcon = () => (
    <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 4a8 8 0 0 1 12 0M4 4v4h4M16 16a8 8 0 0 1-12 0M16 16v-4h-4" />
    </svg>
);

function collectAllCodes(nodes: IndustryNode[]): Set<string> {
    const set = new Set<string>();
    const walk = (list: IndustryNode[]) => {
        list.forEach(n => { set.add(n.code); walk(n.children); });
    };
    walk(nodes);
    return set;
}

function filterTree(nodes: IndustryNode[], query: string): IndustryNode[] {
    if (!query) return nodes;
    const q = query.toLowerCase();
    const keep = (node: IndustryNode): IndustryNode | null => {
        const filteredChildren = node.children.map(keep).filter(Boolean) as IndustryNode[];
        if (node.descrip.toLowerCase().includes(q) || node.code.toLowerCase().includes(q) || filteredChildren.length > 0) {
            return { ...node, children: filteredChildren };
        }
        return null;
    };
    return nodes.map(keep).filter(Boolean) as IndustryNode[];
}

interface TreeNodeProps {
    node: IndustryNode;
    depth: number;
    expandedNodes: Set<string>;
    selectedCode: string | null;
    onToggle: (code: string) => void;
    onSelect: (node: IndustryNode) => void;
    query: string;
}

const TreeNode: React.FC<TreeNodeProps> = ({
    node, depth, expandedNodes, selectedCode, onToggle, onSelect, query
}) => {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedNodes.has(node.code);
    const isSelected = selectedCode === node.code;

    const highlight = (text: string) => {
        if (!query) return <span>{text}</span>;
        const idx = text.toLowerCase().indexOf(query.toLowerCase());
        if (idx === -1) return <span>{text}</span>;
        return (
            <span>
                {text.slice(0, idx)}
                <mark style={{
                    background: 'var(--highlight)',
                    color: 'var(--highlight-text)',
                    borderRadius: '2px',
                    padding: '0 2px',
                }}>
                    {text.slice(idx, idx + query.length)}
                </mark>
                {text.slice(idx + query.length)}
            </span>
        );
    };

    return (
        <div>
            <div
                onClick={() => {
                    if (hasChildren) onToggle(node.code);
                    onSelect(node);
                }}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: `5px 10px 5px ${12 + depth * 18}px`,
                    borderRadius: '6px',
                    cursor: 'pointer',
                    userSelect: 'none',
                    fontSize: depth === 0 ? '13px' : '12.5px',
                    fontWeight: depth === 0 ? 500 : 400,
                    color: isSelected ? 'var(--accent)' : depth === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
                    background: isSelected ? 'var(--selected-bg)' : 'transparent',
                    transition: 'background 120ms ease, color 120ms ease',
                    position: 'relative',
                    margin: '1px 0',
                }}
                onMouseEnter={e => {
                    if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = 'var(--hover-bg)';
                }}
                onMouseLeave={e => {
                    if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = 'transparent';
                }}
            >
                {isSelected && (
                    <div style={{
                        position: 'absolute',
                        left: 0,
                        top: '4px',
                        bottom: '4px',
                        width: '3px',
                        background: 'var(--accent)',
                        borderRadius: '0 2px 2px 0',
                    }} />
                )}

                <span style={{ color: isSelected ? 'var(--accent)' : 'var(--text-muted)', display: 'flex' }}>
                    {hasChildren ? <ChevronRight open={isExpanded} /> : <DotIcon />}
                </span>

                <span style={{
                    flex: 1,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    lineHeight: 1.4,
                }}>
                    {highlight(node.descrip)}
                </span>

                {hasChildren && (
                    <span style={{
                        fontSize: '10px',
                        fontWeight: 500,
                        color: 'var(--text-muted)',
                        background: 'var(--pill-bg)',
                        padding: '1px 6px',
                        borderRadius: '10px',
                        flexShrink: 0,
                        letterSpacing: '0.02em',
                    }}>
                        {node.children.length}
                    </span>
                )}
            </div>

            {hasChildren && isExpanded && (
                <div style={{
                    borderLeft: '1px solid var(--indent-line)',
                    marginLeft: `${20 + depth * 18}px`,
                    paddingLeft: '4px',
                }}>
                    {node.children.map(child => (
                        <TreeNode
                            key={child.code}
                            node={child}
                            depth={depth + 1}
                            expandedNodes={expandedNodes}
                            selectedCode={selectedCode}
                            onToggle={onToggle}
                            onSelect={onSelect}
                            query={query}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

const IndustrialCodePage: React.FC<IndustrialCodePageProps> = ({ onSelect }) => {
    const [treeData, setTreeData] = useState<IndustryNode[]>([]);
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['1.2']));
    const [selectedCode, setSelectedCode] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [query, setQuery] = useState('');

    const fetchTreeData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const response = await fetch(
                `${import.meta.env.VITE_API_URL}/MasterData/api/industry`,
                { credentials: 'include' }
            );
            if (!response.ok) throw new Error('Failed to fetch industry data');
            const data = await response.json();
            setTreeData(data.data);
        } catch (err) {
            console.error('Error fetching industry tree:', err);
            setError('Failed to load industry data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchTreeData(); }, [fetchTreeData]);

    useEffect(() => {
        if (query) {
            const allCodes = collectAllCodes(treeData);
            setExpandedNodes(allCodes);
        } else {
            setExpandedNodes(new Set(['1.2']));
        }
    }, [query, treeData]);

    const toggleNode = (code: string) => {
        setExpandedNodes(prev => {
            const next = new Set(prev);
            next.has(code) ? next.delete(code) : next.add(code);
            return next;
        });
    };

    const handleSelect = (node: IndustryNode) => {
        setSelectedCode(node.code);
        onSelect?.(node);
    };

    const expandAll = () => setExpandedNodes(collectAllCodes(treeData));
    const collapseAll = () => setExpandedNodes(new Set());

    const filtered = filterTree(treeData, query);
    const totalNodes = collectAllCodes(treeData).size;

    return (
        <>
            <style>{`
                .industry-tree {
                    --accent:        #2563eb;
                    --accent-light:  #dbeafe;
                    --text-primary:  #111827;
                    --text-secondary:#374151;
                    --text-muted:    #9ca3af;
                    --bg:            #ffffff;
                    --surface:       #f9fafb;
                    --border:        #e5e7eb;
                    --hover-bg:      #f3f4f6;
                    --selected-bg:   #eff6ff;
                    --indent-line:   #e5e7eb;
                    --pill-bg:       #f3f4f6;
                    --highlight:     #fef08a;
                    --highlight-text:#713f12;
                    --search-bg:     #f9fafb;
                    font-family: 'DM Sans', 'Geist', ui-sans-serif, system-ui, sans-serif;
                }

                @media (prefers-color-scheme: dark) {
                    .industry-tree {
                        --accent:        #60a5fa;
                        --accent-light:  #1e3a5f;
                        --text-primary:  #f9fafb;
                        --text-secondary:#d1d5db;
                        --text-muted:    #6b7280;
                        --bg:            #111827;
                        --surface:       #1f2937;
                        --border:        #374151;
                        --hover-bg:      #1f2937;
                        --selected-bg:   #1e3a5f;
                        --indent-line:   #374151;
                        --pill-bg:       #374151;
                        --highlight:     #713f12;
                        --highlight-text:#fef08a;
                        --search-bg:     #1f2937;
                    }
                }

                .industry-tree * { box-sizing: border-box; }

                .industry-search:focus {
                    outline: none;
                    border-color: var(--accent) !important;
                    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 15%, transparent);
                }

                .industry-tree ::-webkit-scrollbar { width: 4px; }
                .industry-tree ::-webkit-scrollbar-track { background: transparent; }
                .industry-tree ::-webkit-scrollbar-thumb {
                    background: var(--border);
                    border-radius: 4px;
                }

                .tree-ctrl-btn {
                    background: none;
                    border: none;
                    padding: 3px 8px;
                    border-radius: 5px;
                    cursor: pointer;
                    font-size: 11px;
                    font-weight: 500;
                    color: var(--text-muted);
                    transition: background 120ms, color 120ms;
                    letter-spacing: 0.02em;
                }
                .tree-ctrl-btn:hover {
                    background: var(--hover-bg);
                    color: var(--text-secondary);
                }

                .retry-btn {
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    margin-top: 10px;
                    padding: 6px 14px;
                    border-radius: 6px;
                    border: 1px solid var(--border);
                    background: var(--bg);
                    color: var(--text-secondary);
                    font-size: 12px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 120ms;
                }
                .retry-btn:hover { background: var(--hover-bg); }
            `}</style>

            <div className="industry-tree" style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                minHeight: 0,
            }}>
                {/* ── header ── */}
                <div style={{
                    padding: '14px 16px 0',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--surface)',
                }}>
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '12px',
                    }}>
                        <div>
                            <p style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                                Industry Code
                            </p>
                            {!loading && !error && (
                                <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--text-muted)' }}>
                                    {totalNodes} entries
                                    {query && filtered.length !== treeData.length
                                        ? ` · ${collectAllCodes(filtered).size} matched`
                                        : ''}
                                </p>
                            )}
                        </div>
                        <div style={{ display: 'flex', gap: '2px' }}>
                            <button className="tree-ctrl-btn" onClick={expandAll} title="Expand all">Expand</button>
                            <button className="tree-ctrl-btn" onClick={collapseAll} title="Collapse all">Collapse</button>
                        </div>
                    </div>

                    {/* search */}
                    <div style={{ position: 'relative', marginBottom: '12px' }}>
                        <span style={{
                            position: 'absolute', left: '10px', top: '50%',
                            transform: 'translateY(-50%)', color: 'var(--text-muted)',
                            pointerEvents: 'none', display: 'flex',
                        }}>
                            <SearchIcon />
                        </span>
                        <input
                            className="industry-search"
                            type="text"
                            placeholder="Search industry codes…"
                            value={query}
                            onChange={e => setQuery(e.target.value)}
                            style={{
                                width: '100%',
                                padding: '7px 10px 7px 32px',
                                background: 'var(--search-bg)',
                                border: '1px solid var(--border)',
                                borderRadius: '7px',
                                fontSize: '12.5px',
                                color: 'var(--text-primary)',
                                transition: 'border-color 150ms, box-shadow 150ms',
                            }}
                        />
                        {query && (
                            <button
                                onClick={() => setQuery('')}
                                style={{
                                    position: 'absolute', right: '8px', top: '50%',
                                    transform: 'translateY(-50%)',
                                    background: 'none', border: 'none', cursor: 'pointer',
                                    color: 'var(--text-muted)', fontSize: '14px',
                                    lineHeight: 1, padding: '2px',
                                }}
                            >✕</button>
                        )}
                    </div>
                </div>

                <div style={{ flex: 1, overflowY: 'auto', padding: '8px 6px' }}>

                    {loading && (
                        <div style={{
                            display: 'flex', flexDirection: 'column',
                            alignItems: 'center', justifyContent: 'center',
                            gap: '10px', padding: '48px 0', color: 'var(--text-muted)',
                        }}>
                            <div style={{
                                width: '22px', height: '22px',
                                border: '2px solid var(--border)',
                                borderTopColor: 'var(--accent)',
                                borderRadius: '50%',
                                animation: 'spin 0.7s linear infinite',
                            }} />
                            <span style={{ fontSize: '12.5px' }}>Loading…</span>
                            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                        </div>
                    )}

                    {error && !loading && (
                        <div style={{
                            margin: '16px 10px',
                            padding: '14px 16px',
                            background: '#fef2f2',
                            border: '1px solid #fecaca',
                            borderRadius: '8px',
                        }}>
                            <p style={{ margin: 0, fontSize: '12.5px', color: '#dc2626', fontWeight: 500 }}>
                                Unable to load data
                            </p>
                            <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#ef4444' }}>
                                {error}
                            </p>
                            <button className="retry-btn" onClick={fetchTreeData}>
                                <RefreshIcon /> Retry
                            </button>
                        </div>
                    )}

                    {!loading && !error && filtered.length === 0 && (
                        <div style={{
                            display: 'flex', flexDirection: 'column',
                            alignItems: 'center', padding: '40px 0',
                            color: 'var(--text-muted)', gap: '6px',
                        }}>
                            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                                <line x1="8" y1="11" x2="14" y2="11" />
                            </svg>
                            <span style={{ fontSize: '12.5px' }}>
                                {query ? `No results for "${query}"` : 'No industry data available'}
                            </span>
                            {query && (
                                <button className="tree-ctrl-btn" onClick={() => setQuery('')}
                                    style={{ color: 'var(--accent)', marginTop: '4px' }}>
                                    Clear search
                                </button>
                            )}
                        </div>
                    )}

                    {!loading && !error && filtered.length > 0 &&
                        filtered.map(node => (
                            <TreeNode
                                key={node.code}
                                node={node}
                                depth={0}
                                expandedNodes={expandedNodes}
                                selectedCode={selectedCode}
                                onToggle={toggleNode}
                                onSelect={handleSelect}
                                query={query}
                            />
                        ))
                    }
                </div>

                {selectedCode && !loading && (
                    <div style={{
                        borderTop: '1px solid var(--border)',
                        padding: '8px 14px',
                        background: 'var(--surface)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                    }}>
                        <div style={{
                            width: '6px', height: '6px', borderRadius: '50%',
                            background: 'var(--accent)', flexShrink: 0,
                        }} />
                        <span style={{ fontSize: '11.5px', color: 'var(--text-muted)', fontWeight: 500 }}>
                            Selected:
                        </span>
                        <span style={{
                            fontSize: '11.5px', color: 'var(--text-primary)',
                            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                            {selectedCode}
                        </span>
                    </div>
                )}
            </div>
        </>
    );
};

export default IndustrialCodePage;