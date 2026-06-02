import { useEffect, useState, useRef, useCallback } from "react";
import api from "../api/axiosInstance";

interface MenuItem {
	menu_id: string;
	menu_desc: string;
	url?: string;
	menu_parent: string;
	children?: MenuItem[];
}

const EXPANDED_W = 260;
const COLLAPSED_W = 64;

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

  :root {
    /* ── Matches PrecheckingIndividuPage palette exactly ── */
    --sb-bg1:      #0F1D3C;
    --sb-bg2:      #1B3A7A;
    --sb-bg3:      #2D5BE3;
    --sb-accent:   #2D5BE3;
    --sb-active:   #2D5BE3;
    --sb-hover:    rgba(45,91,227,.16);
    --sb-border:   rgba(255,255,255,.08);
    --sb-text:     rgba(255,255,255,.88);
    --sb-muted:    rgba(255,255,255,.42);
    --sb-font:     'Plus Jakarta Sans', sans-serif;
    --sb-radius:   10px;
    --sb-dur:      260ms;
    --sb-ease:     cubic-bezier(.4,0,.2,1);
  }

  /* ── Shell ── */
  .sb-shell {
    position: fixed; top: 0; left: 0; z-index: 40;
    height: 100vh;
    /* Same 3-stop gradient as the prechecking header */
    background: linear-gradient(180deg, var(--sb-bg1) 0%, var(--sb-bg2) 60%, #162d60 100%);
    display: flex; flex-direction: column;
    transition: width var(--sb-dur) var(--sb-ease);
    overflow: hidden;
    box-shadow: 4px 0 32px rgba(15,29,60,.5);
    font-family: var(--sb-font);
    border-right: 1px solid var(--sb-border);
    will-change: width;
  }
  .sb-shell.expanded  { width: ${EXPANDED_W}px; }
  .sb-shell.collapsed { width: ${COLLAPSED_W}px; }

  /* Mobile slide */
  .sb-shell.mobile-closed { transform: translateX(-100%); width: ${EXPANDED_W}px; }
  .sb-shell.mobile-open   { transform: translateX(0);     width: ${EXPANDED_W}px; }
  .sb-shell.mobile-closed,
  .sb-shell.mobile-open   { transition: transform var(--sb-dur) var(--sb-ease); }

  /* ── Logo / header area ── */
  .sb-header {
    position: relative;
    flex-shrink: 0; overflow: hidden;
    border-bottom: 1px solid var(--sb-border);
    background: linear-gradient(135deg, rgba(45,91,227,.18) 0%, rgba(15,29,60,.0) 100%);
  }
  /* Top bar: logo mark + wordmark + toggle */
  .sb-header-top {
    display: flex; align-items: center; gap: 0;
    padding: 0;
    min-height: 64px;
  }
  /* Logo mark: square icon area */
  .sb-logo-mark {
    width: 64px; height: 64px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    position: relative;
    transition: width var(--sb-dur) var(--sb-ease);
  }
  /* When collapsed sidebar is 64px: logo-mark 32px + toggle 32px = 64px exactly */
  .sb-shell.collapsed .sb-logo-mark { width: 32px; }
  .sb-logo-mark-inner {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, #2D5BE3 0%, #1B3A7A 100%);
    border: 2px solid rgba(255,255,255,.18);
    box-shadow: 0 4px 14px rgba(45,91,227,.45);
    display: flex; align-items: center; justify-content: center;
    overflow: hidden; flex-shrink: 0;
    transition: transform var(--sb-dur) var(--sb-ease);
  }
  /* Slide the inner mark to stay centered inside the shrinking logo-mark slot */
  .sb-shell.collapsed .sb-logo-mark-inner { transform: translateX(-4px); }
  .sb-logo-mark-inner img {
    width: 100%; height: 100%; object-fit: cover;
    display: block;
  }
  .sb-logo-mark-inner .sb-logo-fallback {
    font-size: 1rem; font-weight: 800; color: #fff; letter-spacing: -.02em;
    line-height: 1; user-select: none;
  }
  /* Wordmark area */
  .sb-wordmark {
    flex: 1; padding: 0 8px 0 0;
    overflow: hidden;
    transition: opacity var(--sb-dur) var(--sb-ease),
                transform var(--sb-dur) var(--sb-ease),
                max-width var(--sb-dur) var(--sb-ease);
  }
  .sb-shell.collapsed .sb-wordmark {
    opacity: 0; transform: translateX(-6px);
    max-width: 0; padding: 0;
    pointer-events: none;
  }
  .sb-wordmark-title {
    font-size: .92rem; font-weight: 700; color: #fff;
    white-space: nowrap; letter-spacing: -.01em; line-height: 1.2;
  }
  .sb-wordmark-sub {
    font-size: .65rem; font-weight: 500; color: rgba(255,255,255,.45);
    white-space: nowrap; letter-spacing: .04em; text-transform: uppercase;
    margin-top: 1px;
  }
  /* Toggle — sits at the far right INSIDE the header, no absolute overlap */
  .sb-toggle {
    width: 32px; height: 64px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; background: transparent; border: none;
    color: rgba(255,255,255,.45);
    transition: color .15s, background .15s;
    border-radius: 0;
    padding: 0;
  }
  .sb-toggle:hover { color: #fff; background: rgba(255,255,255,.06); }
  .sb-toggle-track {
    width: 22px; height: 22px; border-radius: 7px;
    border: 1.5px solid rgba(255,255,255,.22);
    display: flex; align-items: center; justify-content: center;
    transition: border-color .15s, background .15s;
  }
  .sb-toggle:hover .sb-toggle-track {
    border-color: rgba(255,255,255,.5); background: rgba(255,255,255,.08);
  }
  .sb-toggle svg {
    width: 12px; height: 12px;
    transition: transform var(--sb-dur) var(--sb-ease);
  }
  .sb-shell.collapsed .sb-toggle svg { transform: rotate(180deg); }

  /* ── Scroll area ── */
  .sb-scroll {
    flex: 1; overflow-y: auto; overflow-x: hidden;
    padding: 6px 0 16px;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,.1) transparent;
  }
  .sb-scroll::-webkit-scrollbar { width: 3px; }
  .sb-scroll::-webkit-scrollbar-track { background: transparent; }
  .sb-scroll::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 3px; }

  /* ── Section heading ── */
  .sb-section-head {
    padding: 14px 16px 5px;
    font-size: .6rem; font-weight: 700; letter-spacing: .12em;
    text-transform: uppercase; color: var(--sb-muted);
    white-space: nowrap;
    transition: opacity var(--sb-dur) var(--sb-ease),
                max-height var(--sb-dur) var(--sb-ease),
                padding var(--sb-dur) var(--sb-ease);
  }
  .sb-shell.collapsed .sb-section-head {
    opacity: 0; max-height: 0; padding-top: 0; padding-bottom: 0; overflow: hidden;
  }

  /* ── Menu item row ── */
  .sb-item {
    position: relative;
    display: flex; align-items: center;
    padding: 9px 12px; margin: 2px 8px;
    border-radius: var(--sb-radius);
    cursor: pointer;
    transition: background .15s, color .15s;
    color: var(--sb-text);
    text-decoration: none;
    min-height: 40px;
    overflow: hidden;
    gap: 10px;
  }
  .sb-item:hover  { background: var(--sb-hover); }
  .sb-item.active {
    background: var(--sb-active);
    box-shadow: 0 2px 14px rgba(45,91,227,.45);
    color: #fff;
  }
  .sb-item.active::before {
    content: ''; position: absolute; left: 0; top: 18%; bottom: 18%;
    width: 3px; border-radius: 0 3px 3px 0;
    background: rgba(255,255,255,.7);
  }
  .sb-item.parent-open { background: rgba(45,91,227,.12); }

  /* ── Icon ── */
  .sb-icon {
    width: 20px; height: 20px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    opacity: .8;
  }
  .sb-item.active .sb-icon,
  .sb-item:hover  .sb-icon { opacity: 1; }

  /* ── Label ── */
  .sb-label {
    font-size: .82rem; font-weight: 500;
    white-space: nowrap; flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
    transition: opacity var(--sb-dur) var(--sb-ease),
                transform var(--sb-dur) var(--sb-ease);
}
  .sb-shell.collapsed .sb-label {
    opacity: 0; transform: translateX(-8px); pointer-events: none;
  }

  /* ── Chevron ── */
  .sb-chevron {
    width: 14px; height: 14px; flex-shrink: 0;
    transition: transform .2s var(--sb-ease),
                opacity var(--sb-dur) var(--sb-ease);
    opacity: .5;
  }
  .sb-chevron.open { transform: rotate(90deg); }
  .sb-item:hover .sb-chevron { opacity: .8; }
  .sb-shell.collapsed .sb-chevron { opacity: 0; }

  /* ── Children panel ── */
  .sb-children {
    overflow: hidden;
    transition: max-height .28s var(--sb-ease);
  }

  /* ── Child item ── */
  .sb-child-item {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 12px 7px 14px; margin: 1px 8px 1px 22px;
    border-radius: 8px; cursor: pointer;
    color: var(--sb-muted); font-size: .79rem; font-weight: 500;
    text-decoration: none; white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: background .15s, color .15s;
    position: relative;
  }
  .sb-child-item::before {
    content: ''; position: absolute; left: -8px; top: 50%; transform: translateY(-50%);
    width: 1px; height: 55%; background: rgba(255,255,255,.12); border-radius: 1px;
  }
  .sb-child-item:hover  { background: var(--sb-hover); color: var(--sb-text); }
  .sb-child-item.active {
    background: rgba(45,91,227,.28); color: #fff;
    box-shadow: inset 0 0 0 1px rgba(45,91,227,.4);
  }
  .sb-child-dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: currentColor; flex-shrink: 0; opacity: .45;
    transition: opacity .15s, transform .15s;
  }
  .sb-child-item.active .sb-child-dot,
  .sb-child-item:hover  .sb-child-dot { opacity: 1; transform: scale(1.3); }

  /* ── Tooltip when collapsed ── */
  .sb-item[data-tip]:hover::after {
    content: attr(data-tip);
    position: absolute; left: calc(100% + 12px); top: 50%;
    transform: translateY(-50%);
    /* Same navy as prechecking card */
    background: #1B3A7A; color: #fff; font-size: .75rem; font-weight: 500;
    padding: 5px 12px; border-radius: 8px; white-space: nowrap;
    pointer-events: none; z-index: 200;
    box-shadow: 0 4px 20px rgba(15,29,60,.45);
    border: 1px solid rgba(45,91,227,.3);
    opacity: 0; animation: sb-tip .12s .25s ease forwards;
  }
  @keyframes sb-tip { to { opacity: 1; } }

  /* ── Mobile overlay ── */
  .sb-overlay {
    position: fixed; inset: 0; z-index: 39;
    background: rgba(15,29,60,.6);
    backdrop-filter: blur(3px);
    animation: sb-fade .2s ease;
  }
  @keyframes sb-fade { from { opacity: 0; } to { opacity: 1; } }

  /* ── Mobile hamburger ── */
  .sb-hamburger {
    position: fixed; top: 14px; left: 14px; z-index: 50;
    width: 40px; height: 40px; border-radius: 10px;
    background: #2D5BE3; border: none;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(45,91,227,.5);
    transition: background .15s, transform .12s;
  }
  .sb-hamburger:hover { background: #4472f5; transform: scale(1.05); }
  .sb-hamburger svg { width: 20px; height: 20px; color: #fff; }
`;

if (!document.getElementById("sb-styles")) {
	const s = document.createElement("style");
	s.id = "sb-styles";
	s.textContent = css;
	document.head.appendChild(s);
}

function MenuIcon({ label, size = 18 }: { label: string; size?: number }) {
	const l = label.toLowerCase();
	if (l.includes("dashboard") || l.includes("home"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" /></svg>;
	if (l.includes("setting") || l.includes("config") || l.includes("parameter"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" /></svg>;
	if (l.includes("user") || l.includes("customer") || l.includes("nasabah") || l.includes("pelanggan"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z" /></svg>;
	if (l.includes("report") || l.includes("laporan") || l.includes("analytic"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" /></svg>;
	if (l.includes("prechecking") || l.includes("check") || l.includes("verif"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>;
	if (l.includes("cam") || l.includes("loan") || l.includes("kredit") || l.includes("pembiayaan"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" /></svg>;
	if (l.includes("payment") || l.includes("bayar") || l.includes("transaksi"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" /></svg>;
	if (l.includes("master") || l.includes("data"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z" /><path d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z" /><path d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z" /></svg>;
	if (l.includes("monitor") || l.includes("status"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M3 5a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2h-2.22l.123.489.804.804A1 1 0 0113 18H7a1 1 0 01-.707-1.707l.804-.804L7.22 15H5a2 2 0 01-2-2V5zm5.771 7H5V5h10v7H8.771z" clipRule="evenodd" /></svg>;
	if (l.includes("approve") || l.includes("persetujuan"))
		return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>;
	return <svg width={size} height={size} viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" /></svg>;
}

function MenuNode({
	item, collapsed, depth = 0, resetKey,
}: {
	item: MenuItem; collapsed: boolean; depth?: number; resetKey: number;
}) {
	const currentPath = window.location.pathname;
	const normalizedUrl = item.url ? normalizeUrl(item.url) : null;
	const isActive = !!normalizedUrl && currentPath === normalizedUrl;
	const hasChildren = !!item.children?.length;

	const hasActiveChild = hasChildren && item.children!.some(
		(c) => c.url && currentPath === normalizeUrl(c.url)
	);
	const [open, setOpen] = useState(hasActiveChild);

	useEffect(() => {
		if (resetKey > 0) setOpen(false);
	}, [resetKey]);

	const toggle = () => setOpen((p) => !p);
	const childCount = item.children?.length ?? 0;
	const childPanelH = (open && !collapsed) ? 2000 : 0;

	if (depth === 0) {
		const row = (
			<div
				className={`sb-item${isActive ? " active" : ""}${open && hasChildren ? " parent-open" : ""}`}
				data-tip={collapsed ? item.menu_desc : undefined}
				onClick={hasChildren ? toggle : undefined}
				style={{ cursor: hasChildren || normalizedUrl ? "pointer" : "default" }}
			>
				<span className="sb-icon"><MenuIcon label={item.menu_desc} /></span>
				<span className="sb-label" title={item.menu_desc}>{item.menu_desc}</span>
				{hasChildren && (
					<svg className={`sb-chevron${open ? " open" : ""}`} viewBox="0 0 20 20" fill="currentColor">
						<path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
					</svg>
				)}
			</div>
		);

		return (
			<li style={{ listStyle: "none" }}>
				{normalizedUrl && !hasChildren
					? <a href={normalizedUrl} target="main1" style={{ textDecoration: "none" }}>{row}</a>
					: row
				}
				{hasChildren && (
					<div
						className="sb-children"
						style={{ maxHeight: childPanelH, overflow: "hidden", transition: "max-height .28s cubic-bezier(.4,0,.2,1)" }}
					>
						<ul style={{ padding: 0, margin: "2px 0" }}>
							{item.children!.map((child) => (
								<MenuNode key={child.menu_id} item={child} collapsed={collapsed} depth={1} resetKey={resetKey} />
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
					<div className={`sb-child-item${childActive ? " active" : ""}`} onClick={toggle} title={item.menu_desc} >
						<span className="sb-child-dot" />
						<span style={{ flex: 1, whiteSpace: "nowrap" }}>{item.menu_desc}</span>
						<svg
							style={{
								width: 12, height: 12, opacity: .45, flexShrink: 0,
								transform: open ? "rotate(90deg)" : "none", transition: "transform .2s"
							}}
							viewBox="0 0 20 20" fill="currentColor"
						>
							<path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
						</svg>
					</div>
					<div style={{ maxHeight: (open && !collapsed) ? 2000 : 0, overflow: "hidden", transition: "max-height .25s cubic-bezier(.4,0,.2,1)" }}>
						<ul style={{ padding: "0 0 0 10px", margin: 0 }}>
							{item.children!.map((c) => (
								<MenuNode key={c.menu_id} item={c} collapsed={collapsed} depth={2} resetKey={resetKey} />
							))}
						</ul>
					</div>
				</>
			) : (
				<a href={childUrl} target="main1" className={`sb-child-item${childActive ? " active" : ""}`} title={item.menu_desc} >
					<span className="sb-child-dot" />
					{item.menu_desc}
				</a>
			)}
		</li>
	);
}

export default function Sidebar() {

	if (window.self !== window.top) return null;
	const [menuTree, setMenuTree] = useState<MenuItem[]>([]);
	const [collapsed, setCollapsed] = useState(() => {
		const saved = localStorage.getItem("sb-collapsed");
		return saved === "1";
	});
	const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
	const [mobileOpen, setMobileOpen] = useState(false);
	const [resetKey, setResetKey] = useState(0);
	const sidebarRef = useRef<HTMLDivElement>(null);


	useEffect(() => {
		const check = () => {
			const mobile = window.innerWidth < 768;
			setIsMobile(mobile);
			if (!mobile) setMobileOpen(false);
		};
		window.addEventListener("resize", check);
		return () => window.removeEventListener("resize", check);
	}, []);

	useEffect(() => {
		const handler = (e: MouseEvent) => {
			if (isMobile && mobileOpen && sidebarRef.current && !sidebarRef.current.contains(e.target as Node))
				setMobileOpen(false);
		};
		document.addEventListener("mousedown", handler);
		return () => document.removeEventListener("mousedown", handler);
	}, [isMobile, mobileOpen]);

	useEffect(() => {
		api.get('/api/menus')
			.then((r) => setMenuTree(buildTree(r.data)))
			.catch((e) => console.error("Failed to load menus:", e));
	}, []);

	useEffect(() => {
		const saved = localStorage.getItem("sb-collapsed");
		if (saved !== null) setCollapsed(saved === "1");
	}, []);

	const toggleCollapsed = useCallback(() => {
		setCollapsed((prev) => {
			const next = !prev;
			localStorage.setItem("sb-collapsed", next ? "1" : "0");
			return next;
		});
		setResetKey((k) => k + 1);
	}, []);

	const sidebarCls = isMobile
		? (mobileOpen ? "sb-shell mobile-open" : "sb-shell mobile-closed")
		: (collapsed ? "sb-shell collapsed" : "sb-shell expanded");

	const currentW = isMobile ? EXPANDED_W : (collapsed ? COLLAPSED_W : EXPANDED_W);

	return (
		<>
			{/* ── Mobile hamburger ── */}
			{isMobile && (
				<button className="sb-hamburger" onClick={() => setMobileOpen((p) => !p)} aria-label="Toggle menu">
					{mobileOpen ? (
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
							<line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
						</svg>
					) : (
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
							<line x1="3" y1="6" x2="21" y2="6" />
							<line x1="3" y1="12" x2="21" y2="12" />
							<line x1="3" y1="18" x2="21" y2="18" />
						</svg>
					)}
				</button>
			)}

			{/* ── Mobile overlay ── */}
			{isMobile && mobileOpen && (
				<div className="sb-overlay" onClick={() => setMobileOpen(false)} />
			)}

			{/* ── Sidebar shell ── */}
			<div ref={sidebarRef} className={sidebarCls} style={{ position: "fixed" }}>

				{/* ── Header: logo + wordmark + toggle (all inline, no absolute) ── */}
				<div className="sb-header">
					<div className="sb-header-top">

						{/* Logo mark with image + graceful fallback */}
						<div className="sb-logo-mark">
							<div className="sb-logo-mark-inner">
								<img
									src="/images/new_logo_genie.png"
									alt=""
									onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
								/>
								<span className="sb-logo-fallback">G</span>
							</div>
						</div>

						{/* Wordmark */}
						<div className="sb-wordmark">
							<div className="sb-wordmark-title">Genie</div>
							<div className="sb-wordmark-sub">CAM</div>
						</div>

						{/* Toggle — desktop only, sits inline at far right */}
						{!isMobile && (
							<button className="sb-toggle" onClick={toggleCollapsed} aria-label="Toggle sidebar">
								<div className="sb-toggle-track">
									<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={2.5}
										strokeLinecap="round" strokeLinejoin="round">
										<path d="M13 5l-5 5 5 5" />
									</svg>
								</div>
							</button>
						)}
					</div>
				</div>

				{/* Scroll + menu */}
				<div className="sb-scroll">
					<div className="sb-section-head">Navigation</div>
					<ul style={{ padding: 0, margin: 0 }}>
						{menuTree.map((item) => (
							<MenuNode
								key={item.menu_id}
								item={item}
								collapsed={collapsed && !isMobile}
								resetKey={resetKey}
							/>
						))}
					</ul>
				</div>
			</div>

			{/* Spacer — pushes page content right by the sidebar width */}
			{!isMobile && (
				<div style={{ width: currentW, flexShrink: 0, transition: `width 260ms cubic-bezier(.4,0,.2,1)` }} />
			)}
		</>
	);
}

function buildTree(items: MenuItem[]): MenuItem[] {
	const map: Record<string, MenuItem> = {};
	const roots: MenuItem[] = [];
	items.forEach((i) => (map[i.menu_id] = { ...i, children: [] }));
	items.forEach((i) => {
		if (i.menu_parent && i.menu_parent !== "0") {
			map[i.menu_parent]?.children?.push(map[i.menu_id]);
		} else {
			roots.push(map[i.menu_id]);
		}
	});
	return roots;
}

function normalizeUrl(oldUrl: string): string {
	if (!oldUrl) return "#";
	return (
		"/" +
		oldUrl
			.replace(/^(module_cam|module_other|module_h2h|module_espay|module_ojk|module_hr)\//, "")
			.replace(/\.php$/, "")
			.replace(/_/g, "-")
	);
}