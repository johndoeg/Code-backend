import { useEffect, useState, useRef, useCallback } from "react";
import { Link, useLocation, useNavigate, type Location } from "react-router-dom";
import { MODAL_ROUTES } from "../config/modalRoutes";
import api from "../api/axiosInstance";
import { useAuth } from "../contexts/AuthContext";

interface MenuItem {
	menu_id: string;
	menu_desc: string;
	url?: string;
	menu_parent: string;
	children?: MenuItem[];
}

interface SidebarProps {
    open: boolean;
    mini: boolean;
    onClose: () => void;
}

const EXPANDED_W = 260;
const COLLAPSED_W = 52;

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

  :root {
    --sb-bg:      #1a1a1a;
    --sb-hover:   rgba(255,255,255,.07);
    --sb-active:  rgba(255,255,255,.11);
    --sb-border:  rgba(255,255,255,.08);
    --sb-text:    rgba(255,255,255,.85);
    --sb-muted:   rgba(255,255,255,.38);
    --sb-accent:  #cc7a29;
    --sb-font:    'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --sb-dur:     220ms;
    --sb-ease:    cubic-bezier(.4,0,.2,1);
  }

  /* ── Sidebar shell ── */
  .sb-shell {
    position: fixed; top: 0; left: 0; z-index: 40;
    height: 100vh;
    height: 100dvh;
    background: var(--sb-bg);
    display: flex; flex-direction: column;
    border-right: 1px solid var(--sb-border);
    font-family: var(--sb-font);
    overflow: hidden;
    transition: width var(--sb-dur) var(--sb-ease);
    will-change: width;
  }
  .sb-shell.expanded  { width: ${EXPANDED_W}px; }
  .sb-shell.collapsed { width: ${COLLAPSED_W}px; cursor: pointer; }

  /* mobile overrides — sidebar always full-width, slides in/out */
  .sb-shell.mobile-open {
    width: ${EXPANDED_W}px;
    max-width: 85vw;
    transform: translateX(0);
    transition: transform var(--sb-dur) var(--sb-ease);
    z-index: 9998;
    box-shadow: 4px 0 24px rgba(0,0,0,.35);
  }
  .sb-shell.mobile-closed {
    width: ${EXPANDED_W}px;
    max-width: 85vw;
    transform: translateX(-100%);
    transition: transform var(--sb-dur) var(--sb-ease);
    z-index: 9998;
  }

  /* ── Header ── */
  .sb-header {
    flex-shrink: 0;
    display: flex; align-items: center;
    height: 100px; padding: 0 4px 0 12px;
    border-bottom: 1px solid var(--sb-border);
    position: relative; z-index: 1;
  }

  /* Genie home link */
  .sb-header-link {
    flex: 1; display: flex; align-items: center; gap: 10px;
    overflow: hidden; min-width: 0; text-decoration: none;
    border-radius: 7px; padding: 4px 6px 4px 0; margin-left: -2px;
    transition: background .12s, opacity var(--sb-dur), max-width var(--sb-dur), transform var(--sb-dur);
  }
  .sb-header-link:hover { background: var(--sb-hover); }
  .sb-shell.collapsed .sb-header-link {
    opacity: 0; max-width: 0; transform: translateX(-8px); pointer-events: none; padding: 0;
  }
  .sb-header-content:hover .sb-appname-title { color: #fff; }
  .sb-header-content:hover .sb-logo { opacity: .85; }

  /* Toggle button on the RIGHT */
  .sb-toggle-btn {
    width: ${COLLAPSED_W}px; height: 52px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    background: transparent; border: none;
    cursor: pointer; color: var(--sb-muted);
    transition: color .12s, background .12s;
    border-radius: 0; position: relative;
  }
  .sb-toggle-btn:hover { color: var(--sb-text); background: var(--sb-hover); }
  .sb-toggle-btn svg { width: 18px; height: 18px; }

  /* Tooltip */
  .sb-tip {
    position: fixed;
    background: #2c2c2c; border: 1px solid var(--sb-border);
    border-radius: 7px; padding: 6px 10px;
    white-space: nowrap; pointer-events: none; z-index: 9999;
    opacity: 0; transition: opacity .1s .25s;
    display: flex; flex-direction: column; align-items: center; gap: 4px;
  }
  .sb-toggle-btn:hover .sb-tip { opacity: 1; }
  .sb-tip-label { font-size: .74rem; font-weight: 500; color: var(--sb-text); line-height: 1; }
  .sb-tip-kbd {
    font-size: .68rem; color: var(--sb-muted); line-height: 1;
    display: flex; align-items: center; gap: 3px;
  }
  .sb-tip-kbd kbd {
    background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.18);
    border-radius: 4px; padding: 1px 5px;
    font-family: var(--sb-font); font-size: .67rem; color: rgba(255,255,255,.55);
  }

  .sb-logo {
    width: 26px; height: 26px; border-radius: 6px; flex-shrink: 0;
    background: var(--sb-accent);
    display: flex; align-items: center; justify-content: center; overflow: hidden;
  }
  .sb-logo img { width: 17px; height: 17px; object-fit: contain; display: block; }
  .sb-logo-fb  { font-size: .8rem; font-weight: 700; color: #fff; letter-spacing: -.02em; display: none; }
  .sb-logo img[style*="none"] ~ .sb-logo-fb { display: block; }
  .sb-appname  { flex: 1; overflow: hidden; min-width: 0; }
  .sb-appname-title { font-size: 1rem; font-weight: 600; color: var(--sb-text); white-space: nowrap; line-height: 1.2; }
  .sb-appname-sub   { font-size: .8rem; color: var(--sb-muted); white-space: nowrap; text-transform: uppercase; letter-spacing: .06em; margin-top: 1px; }

  /* ── Nav scroll ── */
  .sb-scroll {
    flex: 1; overflow-y: auto; overflow-x: hidden;
    padding: 4px 0 12px;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,.08) transparent;
  }
  .sb-scroll::-webkit-scrollbar { width: 3px; }
  .sb-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,.08); border-radius: 3px; }

  .sb-section-head {
    padding: 14px 14px 4px;
    font-size: .6rem; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: var(--sb-muted); white-space: nowrap;
    transition: opacity var(--sb-dur), max-height var(--sb-dur), padding var(--sb-dur);
  }
  .sb-shell.collapsed .sb-section-head {
    opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; overflow: hidden;
  }

  /* ── Nav items ── */
  .sb-item {
    position: relative;
    display: flex; align-items: center; gap: 0;
    margin: 1px 6px; height: 36px;
    border-radius: 8px; cursor: pointer;
    color: var(--sb-text); text-decoration: none;
    transition: background .12s; overflow: hidden;
  }
  .sb-item:hover  { background: var(--sb-hover); }
  .sb-item.active { background: var(--sb-active); }

  .sb-icon {
    width: ${COLLAPSED_W - 12}px; height: 36px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    color: var(--sb-muted); transition: color .12s;
  }
  .sb-item:hover .sb-icon, .sb-item.active .sb-icon { color: var(--sb-text); }

  .sb-label {
    font-size: 1rem; font-weight: 500;
    white-space: nowrap; flex: 1; overflow: hidden; text-overflow: ellipsis;
    transition: opacity var(--sb-dur), transform var(--sb-dur);
  }
  .sb-shell.collapsed .sb-label { opacity: 0; transform: translateX(-6px); pointer-events: none; }

  .sb-chevron {
    width: 14px; height: 14px; flex-shrink: 0; margin-right: 8px;
    color: var(--sb-muted); opacity: 0;
    transition: transform .18s var(--sb-ease), opacity .12s;
  }
  .sb-item:hover .sb-chevron { opacity: 1; }
  .sb-chevron.open { transform: rotate(90deg); opacity: 1; }
  .sb-shell.collapsed .sb-chevron { opacity: 0 !important; }

  .sb-shell.collapsed .sb-item[data-tip]:hover::after {
    content: attr(data-tip);
    position: absolute; left: calc(100% + 8px); top: 50%; transform: translateY(-50%);
    background: #2c2c2c; color: var(--sb-text); font-size: .75rem; font-weight: 500;
    padding: 4px 10px; border-radius: 6px; white-space: nowrap;
    pointer-events: none; z-index: 200;
    border: 1px solid var(--sb-border);
    opacity: 0; animation: sbtip .1s .15s ease forwards;
  }
  @keyframes sbtip { to { opacity: 1; } }

  /* ── Children ── */
  .sb-children { overflow: hidden; transition: max-height .24s var(--sb-ease); }
  .sb-child-item {
    display: flex; align-items: center; gap: 10px;
    height: 32px; padding: 0 8px 0 12px;
    margin: 1px 6px 1px 28px; border-radius: 7px;
    cursor: pointer; color: var(--sb-muted);
    font-size: .85rem; font-weight: 400;
    text-decoration: none; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
    transition: background .12s, color .12s;
  }
  .sb-child-item:hover  { background: var(--sb-hover); color: var(--sb-text); }
  .sb-child-item.active { background: var(--sb-active); color: var(--sb-text); }
  .sb-child-dot {
    width: 4px; height: 4px; border-radius: 50%;
    background: currentColor; flex-shrink: 0; opacity: .4;
    transition: opacity .12s;
  }
  .sb-child-item:hover .sb-child-dot,
  .sb-child-item.active .sb-child-dot { opacity: 1; }

  /* ── Footer / Logout ── */
  .sb-footer {
    flex-shrink: 0;
    padding: 6px 6px 8px;
    border-top: 1px solid var(--sb-border);
  }
  .sb-logout {
    width: 100%;
    -webkit-appearance: none; appearance: none;
    border: none; background: #dc3545;
    font: inherit; text-align: left; padding: 0;
  }
  .sb-logout .sb-icon,
  .sb-logout .sb-label {
    color: #fff;
  }
  .sb-logout:hover {
    background: #c4283a;
  }
  .sb-logout:disabled {
    opacity: .75;
    cursor: not-allowed;
  }
  .sb-spin {
    animation: sbspin .8s linear infinite;
  }
  @keyframes sbspin { to { transform: rotate(360deg); } }

  /* ── Mobile overlay ── */
  .sb-overlay {
    position: fixed; inset: 0; z-index: 9997;
    background: rgba(0,0,0,.6);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    animation: sbfade .18s ease;
  }
  @keyframes sbfade { from { opacity: 0; } to { opacity: 1; } }

  /* ── Mobile hamburger ── */
  .sb-hamburger {
    position: fixed; top: 12px; right: 12px; z-index: 9999;
    width: 40px; height: 40px; border-radius: 10px;
    background: var(--sb-bg);
    border: 1px solid var(--sb-border);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(0,0,0,.5);
    transition: background .12s, opacity .16s var(--sb-ease), transform .16s var(--sb-ease);
  }
  .sb-hamburger:hover { background: #242424; }
  .sb-hamburger svg { width: 18px; height: 18px; color: var(--sb-text); }
  .sb-hamburger:active { transform: scale(.94); }
`;

function SidebarLink({
	to,
	className,
	dataTip,
	title,
	style,
	onNavigate,
	navState,
	children,
}: {
	to: string;
	className?: string;
	dataTip?: string;
	title?: string;
	style?: React.CSSProperties;
	onNavigate?: () => void;
	navState?: { background: Location };
	children: React.ReactNode;
}) {
	const navigate = useNavigate();

	const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

		e.preventDefault();
		navigate(to, navState ? { state: navState } : undefined);
		onNavigate?.();
	};

	return (
		<a href="/" className={className} data-tip={dataTip} title={title} style={style} onClick={handleClick}>
			{children}
		</a>
	);
}

if (!document.getElementById("sb-styles")) {
	const s = document.createElement("style");
	s.id = "sb-styles";
	s.textContent = css;
	document.head.appendChild(s);
}

function IconSidebar() {
	return (
		<svg viewBox="0 0 20 20" fill="currentColor">
			<path fillRule="evenodd" clipRule="evenodd"
				d="M3 4a1 1 0 011-1h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm2 1v10h3V5H5zm5 0v10h5V5h-5z" />
		</svg>
	);
}

function IconLogout({ size = 16 }: { size?: number }) {
	return (
		<svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
			<path d="M7.5 17.5H4.5A1.5 1.5 0 013 16V4a1.5 1.5 0 011.5-1.5h3" />
			<path d="M13 14l4-4-4-4" />
			<path d="M17 10H7.5" />
		</svg>
	);
}

function MenuIcon({ label, size = 16 }: { label: string; size?: number }) {
	const l = label.toLowerCase();
	const p = (d: string) => <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" clipRule="evenodd" d={d} /></svg>;
	const pp = (...ds: string[]) => <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor">{ds.map((d, i) => <path key={i} d={d} />)}</svg>;

	if (l.includes("dashboard") || l.includes("home"))
		return p("M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z");
	if (l.includes("setting") || l.includes("config") || l.includes("parameter"))
		return p("M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z");
	if (l.includes("user") || l.includes("nasabah") || l.includes("pelanggan"))
		return pp("M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z");
	if (l.includes("report") || l.includes("laporan") || l.includes("analytic"))
		return pp("M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z");
	if (l.includes("check") || l.includes("verif") || l.includes("prechecking"))
		return p("M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z");
	if (l.includes("cam") || l.includes("loan") || l.includes("kredit") || l.includes("pembiayaan"))
		return pp("M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z");
	if (l.includes("payment") || l.includes("bayar") || l.includes("transaksi") || l.includes("history"))
		return p("M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z");
	if (l.includes("master") || l.includes("data"))
		return pp("M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z", "M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z", "M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z");
	if (l.includes("monitor") || l.includes("status"))
		return p("M3 5a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2h-2.22l.123.489.804.804A1 1 0 0113 18H7a1 1 0 01-.707-1.707l.804-.804L7.22 15H5a2 2 0 01-2-2V5zm5.771 7H5V5h10v7H8.771z");
	if (l.includes("approve") || l.includes("persetujuan"))
		return p("M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z");
	return p("M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z");
}

function MenuNode({ item, collapsed, depth = 0, resetKey, currentPath, onNavigate, modalBackground }: {
	item: MenuItem; collapsed: boolean; depth?: number; resetKey: number; currentPath: string; onNavigate?: () => void; modalBackground: Location;
}) {
	const normalizedUrl = item.url ? normalizeUrl(item.url) : null;
	const isActive = !!normalizedUrl && currentPath === normalizedUrl;
	const hasChildren = !!item.children?.length;
	const hasActiveChild = hasChildren && item.children!.some(c => c.url && currentPath === normalizeUrl(c.url));
	const [open, setOpen] = useState(hasActiveChild);

	useEffect(() => { if (resetKey > 0) setOpen(false); }, [resetKey]);
	useEffect(() => { if (hasActiveChild) setOpen(true); }, [currentPath]);
	const toggle = () => setOpen(p => !p);

	if (depth === 0) {
		const row = (
			<>
				<span className="sb-icon"><MenuIcon label={item.menu_desc} /></span>
				<span className="sb-label" title={item.menu_desc}>{item.menu_desc}</span>
				{hasChildren && (
					<svg className={`sb-chevron${open ? " open" : ""}`} viewBox="0 0 20 20" fill="currentColor">
						<path fillRule="evenodd" clipRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" />
					</svg>
				)}
			</>
		);
		return (
			<li style={{ listStyle: "none" }}>
				{normalizedUrl && !hasChildren
					? <SidebarLink
						to={normalizedUrl}
						className={`sb-item${isActive ? " active" : ""}`}
						dataTip={collapsed ? item.menu_desc : undefined}
						onNavigate={onNavigate}
						navState={normalizedUrl && MODAL_ROUTES.has(normalizedUrl) ? { background: modalBackground } : undefined}
						style={{ textDecoration: "none" }}
					>{row}</SidebarLink>
					: <div className={`sb-item${isActive ? " active" : ""}`}
						data-tip={collapsed ? item.menu_desc : undefined}
						onClick={hasChildren ? toggle : undefined}
						style={{ cursor: hasChildren ? "pointer" : "default" }}>{row}</div>
				}
				{hasChildren && (
					<div className="sb-children" style={{ maxHeight: (open && !collapsed) ? 2000 : 0 }}>
						<ul style={{ padding: 0, margin: "2px 0" }}>
							{item.children!.map(c => (
								<MenuNode
									key={c.menu_id}
									item={c}
									collapsed={collapsed}
									depth={1}
									resetKey={resetKey}
									currentPath={currentPath}
									onNavigate={onNavigate}
									modalBackground={modalBackground}
								/>
							))}
						</ul>
					</div>
				)}
			</li>
		);
	}

	const childUrl = item.url ? normalizeUrl(item.url) : "#";
	const childActive = currentPath === childUrl;
	return (
		<li style={{ listStyle: "none" }}>
			{hasChildren ? (
				<>
					<div className={`sb-child-item${childActive ? " active" : ""}`} onClick={toggle} title={item.menu_desc}>
						<span className="sb-child-dot" />
						<span style={{ flex: 1 }}>{item.menu_desc}</span>
						<svg style={{ width: 12, height: 12, opacity: .4, flexShrink: 0, transform: open ? "rotate(90deg)" : "none", transition: "transform .18s" }} viewBox="0 0 20 20" fill="currentColor">
							<path fillRule="evenodd" clipRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" />
						</svg>
					</div>
					<div style={{ maxHeight: open ? 2000 : 0, overflow: "hidden", transition: "max-height .22s cubic-bezier(.4,0,.2,1)" }}>
						<ul style={{ padding: "0 0 0 10px", margin: 0 }}>
							{item.children!.map(c => (
								<MenuNode
									key={c.menu_id}
									item={c}
									collapsed={collapsed}
									depth={1}
									resetKey={resetKey}
									currentPath={currentPath}
									onNavigate={onNavigate}
									modalBackground={modalBackground}
								/>
							))}
						</ul>
					</div>
				</>
			) : (
				<SidebarLink
					to={childUrl}
					className={`sb-child-item${childActive ? " active" : ""}`}
					title={item.menu_desc}
					onNavigate={onNavigate}
					navState={MODAL_ROUTES.has(childUrl) ? { background: modalBackground } : undefined}
					style={{ textDecoration: "none" }}
				>
					<span className="sb-child-dot" />
					{item.menu_desc}
				</SidebarLink>
			)}
		</li>
	);
}

export default function Sidebar({ open: _open, mini: _mini, onClose: _onClose }: SidebarProps) {
		
	if (window.self !== window.top) return null;

	const navigate = useNavigate();
	const location = useLocation();
	const currentPath = location.pathname;
	const { logout } = useAuth();
	const [menuTree, setMenuTree] = useState<MenuItem[]>([]);
	const [collapsed, setCollapsed] = useState(() => localStorage.getItem("sb-collapsed") === "1");
	const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
	const [mobileOpen, setMobileOpen] = useState(false);
	const [resetKey, setResetKey] = useState(0);
	const [isLoggingOut, setIsLoggingOut] = useState(false);
	const sidebarRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const check = () => {
			const m = window.innerWidth < 768;
			setIsMobile(m);
			if (!m) setMobileOpen(false);
		};
		window.addEventListener("resize", check);
		return () => window.removeEventListener("resize", check);
	}, []);

	useEffect(() => {
		const h = (e: MouseEvent) => {
			if (isMobile && mobileOpen && sidebarRef.current && !sidebarRef.current.contains(e.target as Node))
				setMobileOpen(false);
		};
		document.addEventListener("mousedown", h);
		return () => document.removeEventListener("mousedown", h);
	}, [isMobile, mobileOpen]);

	useEffect(() => {
		api.get('/api/menus')
			.then(r => setMenuTree(buildTree(r.data)))
			.catch(e => console.error("Failed to load menus:", e));
	}, []);

	const toggle = useCallback(() => {
		if (isMobile) {
			setMobileOpen(prev => !prev);
		} else {
			setCollapsed(prev => {
				const next = !prev;
				localStorage.setItem("sb-collapsed", next ? "1" : "0");
				return next;
			});
			setResetKey(k => k + 1);
		}
	}, [isMobile]);

	const expandSidebar = useCallback(() => {
		if (isMobile || !collapsed) return;
		setCollapsed(false);
		localStorage.setItem("sb-collapsed", "0");
		setResetKey(k => k + 1);
	}, [isMobile, collapsed]);

	const handleShellClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
		const target = e.target as HTMLElement;
		if (target.closest('.sb-item, .sb-child-item, .sb-toggle-btn, .sb-header-link, a, button')) return;
		expandSidebar();
	}, [expandSidebar]);

	useEffect(() => {
		const onKey = (e: KeyboardEvent) => {
			if (e.ctrlKey && e.key === ".") { e.preventDefault(); toggle(); }
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [toggle]);

	const handleMobileNavigate = useCallback(() => {
		if (isMobile) setMobileOpen(false);
	}, [isMobile]);

	const handleLogout = useCallback(async () => {
		if (isLoggingOut) return;
		if (!confirm("Are you sure you want to log out?")) return;

		setIsLoggingOut(true);
		try {
			await logout();
		} catch (e) {
			console.error("Logout failed:", e);
		} finally {
			setIsLoggingOut(false);
			navigate("/login", { replace: true });
		}
	}, [isLoggingOut, logout, navigate]);

	const sidebarCls = isMobile
		? (mobileOpen ? "sb-shell mobile-open" : "sb-shell mobile-closed")
		: (collapsed ? "sb-shell collapsed" : "sb-shell expanded");

	const currentW = isMobile ? 0 : (collapsed ? COLLAPSED_W : EXPANDED_W);

	return (
		<>
			{isMobile && !mobileOpen && (
				<button
					className="sb-hamburger"
					onClick={() => setMobileOpen(true)}
					aria-label="Open menu"
					aria-expanded={false}
				>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
						<line x1="3" y1="6" x2="21" y2="6" />
						<line x1="3" y1="12" x2="21" y2="12" />
						<line x1="3" y1="18" x2="21" y2="18" />
					</svg>
				</button>
			)}

			{isMobile && mobileOpen && (
				<div className="sb-overlay" onClick={() => setMobileOpen(false)} />
			)}

			<div ref={sidebarRef} className={sidebarCls} onClick={handleShellClick}>

				<div className="sb-header">
					<Link to="/" className="sb-header-link" aria-label="Go to home" onClick={handleMobileNavigate}>
						<div className="sb-logo" aria-hidden="true">
							<img src="/images/new_logo_genie.png" alt=""
								onError={e => { (e.currentTarget as HTMLImageElement).style.display = "none"; }} />
							<span className="sb-logo-fb">G</span>
						</div>
						<div className="sb-appname">
							<div className="sb-appname-title">Genie</div>
							<div className="sb-appname-sub">CAM</div>
						</div>
					</Link>

					{!isMobile && (
						<button
							className="sb-toggle-btn"
							onClick={toggle}
							aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
							onMouseEnter={e => {
								const tip = (e.currentTarget as HTMLElement).querySelector<HTMLElement>(".sb-tip");
								if (!tip) return;
								const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
								tip.style.top = (r.bottom + 8) + "px";
								tip.style.left = Math.max(8, r.left + r.width / 2 - 70) + "px";
							}}
						>
							<IconSidebar />
							<span className="sb-tip">
								<span className="sb-tip-label">{collapsed ? "Open sidebar" : "Close sidebar"}</span>
								<span className="sb-tip-kbd"><kbd>Ctrl</kbd><span>+</span><kbd>.</kbd></span>
							</span>
						</button>
					)}

					{isMobile && (
						<button
							className="sb-toggle-btn"
							onClick={() => setMobileOpen(false)}
							aria-label="Close sidebar"
						>
							<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
								<line x1="18" y1="6" x2="6" y2="18" />
								<line x1="6" y1="6" x2="18" y2="18" />
							</svg>
						</button>
					)}
				</div>

				<div className="sb-scroll">
					<div className="sb-section-head">Menu</div>
					<ul style={{ padding: 0, margin: 0 }}>
						{menuTree.map(item => (
							<MenuNode
								key={item.menu_id}
								item={item}
								collapsed={collapsed && !isMobile}
								resetKey={resetKey}
								currentPath={currentPath}
								onNavigate={handleMobileNavigate}
								modalBackground={location}
							/>
						))}
					</ul>
				</div>

				<div className="sb-footer">
					<button
						type="button"
						className="sb-item sb-logout"
						data-tip={(collapsed && !isMobile) ? "Logout" : undefined}
						onClick={handleLogout}
						disabled={isLoggingOut}
					>
						<span className="sb-icon">
							{isLoggingOut
								? <svg className="sb-spin" width={16} height={16} viewBox="0 0 24 24" fill="none">
									<circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity=".25" />
									<path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
								</svg>
								: <IconLogout />}
						</span>
						<span className="sb-label">{isLoggingOut ? "Logging out..." : "Logout"}</span>
					</button>
				</div>
			</div>

			{!isMobile && (
				<div style={{ width: currentW, flexShrink: 0, transition: `width 220ms cubic-bezier(.4,0,.2,1)` }} />
			)}
		</>
	);
}

function buildTree(items: MenuItem[]): MenuItem[] {
	const map: Record<string, MenuItem> = {};
	const roots: MenuItem[] = [];
	items.forEach(i => (map[i.menu_id] = { ...i, children: [] }));
	items.forEach(i => {
		if (i.menu_parent && i.menu_parent !== "0") map[i.menu_parent]?.children?.push(map[i.menu_id]);
		else roots.push(map[i.menu_id]);
	});
	return roots;
}

function normalizeUrl(oldUrl: string): string {
	if (!oldUrl) return "#";
	return "/" + oldUrl
		.replace(/^(module_cam|module_other|module_h2h|module_espay|module_ojk|module_hr)\//, "")
		.replace(/\.php$/, "")
		.replace(/_/g, "-");
}