import { useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowRight, BadgeCheck, Bell, BookOpen, Check, ChevronRight,
  CircleHelp, ClipboardList, Database, Fingerprint, Globe2, KeyRound, LayoutDashboard,
  LockKeyhole, LogOut, Menu, Radio, RefreshCw, Save, Settings2, Shield, ShieldCheck,
  Users, X,
} from 'lucide-react';

const SETUP = [
  { id: 'platform', label: 'Platform identity', icon: Globe2, fields: ['name', 'description'], example: { name: 'DragonForge', description: 'Independent market research and decision support.' } },
  { id: 'policies', label: 'Policies & disclosure', icon: BookOpen, fields: ['terms', 'privacy', 'risk_disclosure'], example: { terms: '', privacy: '', risk_disclosure: 'DragonForge provides market analysis, research, educational information, and decision-support tools only. It does not execute trades or guarantee trading results. Users are solely responsible for their own trading decisions and any resulting gains or losses.' } },
  { id: 'rules', label: 'User & admin rules', icon: Users, fields: ['user_rules', 'admin_rules'], example: { user_rules: [], admin_rules: [] } },
  { id: 'membership', label: 'Membership requirements', icon: BadgeCheck, fields: ['requirements'], example: { requirements: ['verified account', '2FA', 'terms acceptance', 'risk assessment'] } },
  { id: 'subscriptions', label: 'Plans & pricing', icon: ClipboardList, fields: ['plans', 'currency'], example: { plans: [{ name: 'Free' }, { name: 'Pro' }], currency: 'USD' } },
  { id: 'payments', label: 'Payment provider', icon: KeyRound, fields: ['provider', 'configuration_status'], example: { provider: 'Not selected', configuration_status: 'NOT CONFIGURED' } },
  { id: 'trial', label: 'Free-trial configuration', icon: Activity, fields: ['duration_days'], example: { duration_days: 90 } },
  { id: 'notifications', label: 'Notification settings', icon: Bell, fields: ['channels'], example: { channels: ['in-app'] } },
  { id: 'markets', label: 'Supported markets', icon: Globe2, fields: ['supported'], example: { supported: [] } },
  { id: 'strategies', label: 'Strategy configuration', icon: Settings2, fields: ['enabled'], example: { enabled: [] } },
  { id: 'security', label: 'Security settings', icon: Shield, fields: ['session_hours', 'password_min_length'], example: { session_hours: 12, password_min_length: 12 } },
  { id: 'backups', label: 'Backup & recovery', icon: Database, fields: ['frequency', 'retention_days', 'restore_tested'], example: { frequency: 'daily', retention_days: 30, restore_tested: false } },
  { id: 'audit', label: 'Audit logging', icon: ClipboardList, fields: ['enabled'], example: { enabled: true } },
  { id: 'branding', label: 'Platform branding', icon: Fingerprint, fields: ['brand_color'], example: { brand_color: '#c9ed4c' } },
];

const NAV_ITEMS = [
  { id: 'overview', label: 'Owner dashboard', icon: LayoutDashboard },
  { id: 'macro', label: 'Global macro indicators', icon: Activity },
  { id: 'markets', label: 'FX reference rates', icon: Globe2 },
  { id: 'setup', label: 'Platform setup', icon: Settings2 },
  { id: 'admins', label: 'Admins', icon: Users },
  { id: 'security', label: 'Security & sessions', icon: ShieldCheck },
  { id: 'audit', label: 'Audit trail', icon: ClipboardList },
  { id: 'health', label: 'System health', icon: Activity },
];

const LATER_ITEMS = [
  { label: 'Opportunity radar', icon: Radio },
  { label: 'Charts', icon: Activity }, { label: 'Strategies', icon: Settings2 },
  { label: 'Research', icon: BookOpen }, { label: 'Backtesting', icon: ClipboardList },
  { label: 'Paper trading', icon: LayoutDashboard }, { label: 'Journal', icon: BookOpen },
  { label: 'Accounts', icon: Users }, { label: 'Notifications', icon: Bell },
];

const ADMIN_PERMISSIONS = [
  ['applications:review', 'Review membership applications'],
  ['users:support', 'Support users'],
  ['users:status_limited', 'View limited account status'],
  ['security:alerts', 'Review security alerts'],
  ['operations:manage', 'Routine operations'],
];

const RISK_NOTICE = 'DragonForge provides market analysis, research, educational information, and decision-support tools only. It does not execute trades or guarantee trading results. Users are solely responsible for their own trading decisions and any resulting gains or losses.';

async function api(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'include', ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (response.status === 204) return null;
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : result.detail?.message || 'Request failed');
  return result;
}

function IconButton({ children, ...props }) {
  return <button className="icon-button" {...props}>{children}</button>;
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [user, setUser] = useState(null);
  const [section, setSection] = useState('overview');
  const [setupStatus, setSetupStatus] = useState(null);
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [mobileNav, setMobileNav] = useState(false);
  const [authMode, setAuthMode] = useState('');
  const [authForm, setAuthForm] = useState({ bootstrap_token: '', email: '', display_name: '', password: '', totp_code: '' });
  const [selectedSetup, setSelectedSetup] = useState('platform');
  const [configText, setConfigText] = useState(JSON.stringify(SETUP[0].example, null, 2));
  const [reauthPassword, setReauthPassword] = useState('');
  const [totp, setTotp] = useState(null);
  const [totpCode, setTotpCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [auditRows, setAuditRows] = useState([]);
  const [admins, setAdmins] = useState([]);
  const [adminAccess, setAdminAccess] = useState(null);
  const [adminForm, setAdminForm] = useState({ email: '', display_name: '', password: '', permissions: ['users:support'] });
  const [fxData, setFxData] = useState(null);
  const [fxLoading, setFxLoading] = useState(false);
  const [fxError, setFxError] = useState('');
  const [macroData, setMacroData] = useState(null);
  const [macroLoading, setMacroLoading] = useState(false);
  const [macroError, setMacroError] = useState('');

  async function refreshStatus() {
    const data = await api('/status');
    setStatus(data);
    return data;
  }

  async function loadOwnerData() {
    const [setup, system, activeSessions, audit, adminDirectory] = await Promise.all([
      api('/owner/setup'), api('/health'), api('/auth/sessions'), api('/owner/audit?limit=60'), api('/owner/admins'),
    ]);
    setSetupStatus(setup);
    setHealth(system);
    setSessions(activeSessions);
    setAuditRows(audit);
    setAdmins(adminDirectory.admins);
  }

  useEffect(() => {
    let mounted = true;
    async function initialize() {
      try {
        const currentStatus = await refreshStatus();
        if (currentStatus.owner_registered) {
          try {
            const currentUser = await api('/auth/me');
            if (mounted) {
              setUser(currentUser);
              if (currentUser.account_type === 'owner') await loadOwnerData();
              else setAdminAccess(await api('/admin/access'));
            }
          } catch {
            if (mounted) setAuthMode('login');
          }
        } else if (mounted) setAuthMode('bootstrap');
      } catch {
        if (mounted) setError('Platform API is unavailable. Start the DragonForge API and apply its database migrations.');
      }
    }
    initialize();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    if (section !== 'markets') return undefined;
    let cancelled = false;
    setFxLoading(true);
    setFxError('');
    api('/markets/fx')
      .then(data => { if (!cancelled) setFxData(data); })
      .catch(err => { if (!cancelled) setFxError(err.message); })
      .finally(() => { if (!cancelled) setFxLoading(false); });
    return () => { cancelled = true; };
  }, [section]);

  useEffect(() => {
    if (section !== 'macro') return undefined;
    let cancelled = false;
    setMacroLoading(true);
    setMacroError('');
    api('/markets/macro')
      .then(data => { if (!cancelled) setMacroData(data); })
      .catch(err => { if (!cancelled) setMacroError(err.message); })
      .finally(() => { if (!cancelled) setMacroLoading(false); });
    return () => { cancelled = true; };
  }, [section]);

  async function refreshFxData() {
    setFxLoading(true);
    setFxError('');
    try {
      setFxData(await api('/markets/fx'));
    } catch (err) {
      setFxError(err.message);
    } finally {
      setFxLoading(false);
    }
  }

  async function refreshMacroData() {
    setMacroLoading(true);
    setMacroError('');
    try {
      setMacroData(await api('/markets/macro'));
    } catch (err) {
      setMacroError(err.message);
    } finally {
      setMacroLoading(false);
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const path = authMode === 'bootstrap' ? '/auth/bootstrap' : '/auth/login';
      const body = authMode === 'bootstrap'
        ? { bootstrap_token: authForm.bootstrap_token, email: authForm.email, display_name: authForm.display_name, password: authForm.password }
        : { email: authForm.email, password: authForm.password, totp_code: authForm.totp_code || null };
      const currentUser = await api(path, { method: 'POST', body: JSON.stringify(body) });
      setUser(currentUser);
      setAuthMode('');
      if (currentUser.account_type === 'owner') await loadOwnerData();
      else setAdminAccess(await api('/admin/access'));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function startTotp() {
    setBusy(true);
    setError('');
    try {
      const result = await api('/auth/2fa/setup', { method: 'POST', headers: { 'X-Reauth-Password': reauthPassword } });
      setTotp(result);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function enableTotp(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await api('/auth/2fa/enable', { method: 'POST', body: JSON.stringify({ code: totpCode, password: reauthPassword }) });
      setRecoveryCodes(result.recovery_codes);
      setTotp(null);
      setNotice('Two-factor authentication enabled. Save the recovery codes in a secure offline location.');
      await loadOwnerData();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function saveSetup(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const value = JSON.parse(configText);
      await api('/owner/setup', { method: 'PUT', headers: { 'X-Reauth-Password': reauthPassword }, body: JSON.stringify({ section: selectedSetup, value }) });
      setNotice(`${SETUP.find(item => item.id === selectedSetup).label} saved.`);
      await loadOwnerData();
    } catch (err) { setError(err instanceof SyntaxError ? 'Enter valid JSON configuration.' : err.message); }
    finally { setBusy(false); }
  }

  async function publishPlatform() {
    setBusy(true);
    setError('');
    try {
      await api('/owner/publish', { method: 'POST', body: JSON.stringify({ password: reauthPassword }) });
      setNotice('Platform configuration published. Public registration remains disabled until member verification and application review are implemented.');
      await Promise.all([refreshStatus(), loadOwnerData()]);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function logout() {
    await api('/auth/logout', { method: 'POST' }).catch(() => {});
    setUser(null);
    setSetupStatus(null);
    setAuthMode('login');
  }

  async function revokeSession(id) {
    try {
      await api(`/auth/sessions/${id}`, { method: 'DELETE' });
      setSessions(await api('/auth/sessions'));
    } catch (err) { setError(err.message); }
  }

  async function createAdmin(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api('/owner/admins', {
        method: 'POST', headers: { 'X-Reauth-Password': reauthPassword },
        body: JSON.stringify(adminForm),
      });
      setAdminForm({ email: '', display_name: '', password: '', permissions: ['users:support'] });
      setNotice('Administrator account created with the selected permissions.');
      await loadOwnerData();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  function chooseSetup(item) {
    setSelectedSetup(item.id);
    setConfigText(JSON.stringify(setupStatus?.values?.[item.id] || item.example, null, 2));
    setError('');
  }

  if (!status && error) return <div className="fatal-state"><DragonMark /><span className="eyebrow">PLATFORM INITIALIZATION</span><h1>DragonForge is not connected</h1><p>{error}</p><p className="muted">Market feeds, analysis, and execution integrations are not configured.</p><div className="risk-notice">{RISK_NOTICE}</div></div>;
  if (authMode || !user) return <AuthScreen mode={authMode || 'login'} setMode={setAuthMode} form={authForm} setForm={setAuthForm} submit={submitAuth} busy={busy} error={error} status={status} />;
  if (user.account_type === 'admin') return <AdminConsole user={user} access={adminAccess} logout={logout} />;

  const activeSetup = SETUP.find(item => item.id === selectedSetup);
  const selectedNav = NAV_ITEMS.find(item => item.id === section);
  const systemServices = [
    { name: 'Platform API', value: 'AVAILABLE', state: 'healthy', icon: Activity },
    { name: 'PostgreSQL', value: health?.database?.toUpperCase() || 'CHECKING', state: health?.database === 'available' ? 'healthy' : 'warning', icon: Database },
    { name: 'ECB reference data', value: 'DAILY · ON DEMAND', state: 'healthy', icon: Radio },
    { name: 'Analysis engine', value: 'NOT CONFIGURED', state: 'neutral', icon: Activity },
    { name: 'Risk engine', value: 'NOT CONFIGURED', state: 'neutral', icon: Shield },
    { name: 'Backups', value: 'NOT CONFIGURED', state: 'neutral', icon: Database },
  ];

  return (
    <div className="app-shell">
      {mobileNav && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup"><DragonMark /><div><strong>DRAGONFORGE</strong><span>MARKET INTELLIGENCE</span></div><IconButton className="nav-close" aria-label="Close menu" onClick={() => setMobileNav(false)}><X /></IconButton></div>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Owner workspace">
          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return <button key={item.id} className={`nav-item ${section === item.id ? 'nav-item-active' : ''}`} onClick={() => { setSection(item.id); setMobileNav(false); }}><Icon /><span>{item.label}</span>{item.id === 'setup' && setupStatus && !setupStatus.can_publish && <i className="nav-dot" />}</button>;
          })}
        </nav>
        <div className="sidebar-label later-label">PLATFORM MODULES</div>
        <nav className="main-nav muted-nav" aria-label="Modules not configured">
          {LATER_ITEMS.map(item => { const Icon = item.icon; return <div key={item.label} className="nav-item nav-disabled" title="COMING SOON"><Icon /><span>{item.label}</span></div>; })}
        </nav>
        <div className="sidebar-bottom"><span className="owner-mark"><LockKeyhole /> OWNER ACCOUNT</span><span className="owner-email">{user.email}</span><button className="logout-button" onClick={logout}><LogOut /> Sign out</button><span className="version-tag">PHASE 1 · FOUNDATION</span></div>
      </aside>

      <div className="main-column">
        <header className="topbar"><div className="topbar-left"><IconButton className="mobile-menu" aria-label="Open menu" onClick={() => setMobileNav(true)}><Menu /></IconButton><div className="breadcrumb"><span>DragonForge</span><ChevronRight /><strong>{selectedNav?.label || 'Owner dashboard'}</strong></div></div><div className="topbar-right"><div className="data-state"><span className="state-dot" /> ECB DAILY REFERENCE DATA</div><button className="topbar-avatar" aria-label="Owner account" title={user.email}>{user.display_name.slice(0, 1).toUpperCase()}</button></div></header>

        <main className="page-content">
          {error && <div className="inline-alert" role="alert"><AlertTriangle />{error}<button onClick={() => setError('')} aria-label="Dismiss"><X /></button></div>}
          {notice && <div className="inline-success" role="status"><Check />{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X /></button></div>}
          {section === 'macro' && <>
            <div className="page-heading"><div><span className="eyebrow">PUBLIC DATA / GLOBAL ECONOMY</span><h1>Global macro indicators</h1><p>Latest available annual inflation and real GDP growth observations for selected major economies.</p></div><button className="button-secondary" onClick={refreshMacroData} disabled={macroLoading}><RefreshCw />{macroLoading ? 'Refreshing' : 'Refresh indicators'}</button></div>
            <div className="risk-banner"><AlertTriangle /><p>Annual indicators are historical statistics, not real-time market data, forecasts, or investment recommendations. The latest reported year can differ by country and indicator.</p></div>
            {macroError && <div className="inline-alert" role="alert"><AlertTriangle />{macroError}<button onClick={() => setMacroError('')} aria-label="Dismiss"><X /></button></div>}
            {macroLoading && !macroData && <div className="empty-state" role="status">Loading official World Bank observations…</div>}
            {macroData && <>
              <div className="market-source"><div><strong>{macroData.source}</strong><span>{macroData.frequency} · Retrieved {new Date(macroData.fetched_at).toLocaleString()}</span></div><a href={macroData.source_url} target="_blank" rel="noreferrer">Source methodology</a></div>
              <section className="macro-country-grid" aria-label="Annual macroeconomic indicators">
                {macroData.countries.map(country => <article className="macro-country-card" key={country.country_code}>
                  <h2>{country.country}<span>{country.country_code}</span></h2>
                  {country.indicators.map(indicator => <div className="macro-indicator" key={indicator.id}>
                    <span>{indicator.name}</span>
                    <strong>{Number(indicator.value).toFixed(1)}%</strong>
                    <small>{indicator.year}</small>
                  </div>)}
                </article>)}
              </section>
              <p className="market-disclaimer">{macroData.disclaimer}</p>
            </>}
          </>}
          {section === 'markets' && <>
            <div className="page-heading"><div><span className="eyebrow">MARKET DATA / FOREIGN EXCHANGE</span><h1>FX reference rates</h1><p>Official daily reference observations for major US, UK, and Asia-Pacific currencies.</p></div><button className="button-secondary" onClick={refreshFxData} disabled={fxLoading}><RefreshCw />{fxLoading ? 'Refreshing' : 'Refresh rates'}</button></div>
            <div className="risk-banner"><AlertTriangle /><p>ECB reference rates are daily benchmarks, not live trading quotes, and may differ from executable market prices. DragonForge does not connect to bank systems, execute trades, or provide investment advice.</p></div>
            {fxError && <div className="inline-alert" role="alert"><AlertTriangle />{fxError}<button onClick={() => setFxError('')} aria-label="Dismiss"><X /></button></div>}
            {fxLoading && !fxData && <div className="empty-state" role="status">Loading official ECB observations…</div>}
            {fxData && <>
              <div className="market-source"><div><strong>{fxData.source}</strong><span>{fxData.series} · Updated {new Date(fxData.fetched_at).toLocaleString()}</span></div><a href={fxData.source_url} target="_blank" rel="noreferrer">Source methodology</a></div>
              <section className="market-rate-grid" aria-label="ECB exchange rates">
                {fxData.rates.map(rate => <article className="market-rate-card" key={rate.currency}>
                  <div><span>{rate.currency}</span><strong>{rate.name}</strong></div>
                  <b>{Number(rate.units_per_eur).toLocaleString(undefined, { maximumSignificantDigits: 8 })}</b>
                  <small>per 1 EUR · as of {rate.observation_date}</small>
                  <span className={rate.change_pct == null ? 'market-change' : rate.change_pct >= 0 ? 'market-change market-positive' : 'market-change market-negative'}>
                    {rate.change_pct == null ? 'Previous observation unavailable' : `${rate.change_pct >= 0 ? '+' : ''}${rate.change_pct.toFixed(3)}% vs ${rate.previous_observation_date}`}
                  </span>
                </article>)}
              </section>
              <p className="market-disclaimer">{fxData.disclaimer}</p>
            </>}
          </>}
          {section === 'overview' && <>
            <div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / OVERVIEW</span><h1>Platform foundation</h1><p>Identity, security, and launch readiness for DragonForge.</p></div><button className="button-secondary" onClick={() => loadOwnerData().catch(err => setError(err.message))}><RefreshCw /> Refresh status</button></div>
            <div className="risk-banner"><AlertTriangle /><p>{RISK_NOTICE}</p></div>
            <section className="launch-strip"><div className="launch-icon"><ShieldCheck /></div><div className="launch-copy"><span className="eyebrow">LAUNCH CONTROL</span><h2>{status?.published ? 'Platform configuration published' : 'Public registration is disabled'}</h2><p>{status?.published ? 'Member verification and application review are not implemented yet.' : `${setupStatus?.completed_count || 0} of ${setupStatus?.required_count || 14} required setup areas complete.`}</p></div><button className="button-primary" onClick={() => setSection('setup')}>{status?.published ? 'Review setup' : 'Continue setup'}<ArrowRight /></button></section>
            <div className="section-heading"><div><span className="eyebrow">FOUNDATION STATUS</span><h2>System health</h2></div><span className="subtle-label">OPERATIONAL COMPONENTS ONLY</span></div>
            <div className="service-grid">{systemServices.map(item => { const Icon = item.icon; return <div className="service-row" key={item.name}><span className="service-icon"><Icon /></span><div className="service-copy"><strong>{item.name}</strong><span>{item.state === 'neutral' ? 'No provider connected' : item.state === 'healthy' ? 'Responding' : 'Needs attention'}</span></div><span className={`service-state state-${item.state}`}>{item.value}</span></div>; })}</div>
            <section className="setup-progress"><div className="section-heading"><div><span className="eyebrow">OWNER SETUP</span><h2>Launch checklist</h2></div><button className="text-button" onClick={() => setSection('setup')}>Open setup <ArrowRight /></button></div><div className="progress-track"><span style={{ width: `${setupStatus ? (setupStatus.completed_count / setupStatus.required_count) * 100 : 0}%` }} /></div><div className="checklist-grid">{SETUP.map(item => { const done = setupStatus?.sections?.[item.id]?.complete; const Icon = item.icon; return <button key={item.id} className="checklist-item" onClick={() => { chooseSetup(item); setSection('setup'); }}><span className={`check-mark ${done ? 'check-done' : ''}`}>{done ? <Check /> : <Icon />}</span><span>{item.label}</span><ChevronRight /></button>; })}</div></section>
          </>}

          {section === 'setup' && <>
            <div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / CONFIGURATION</span><h1>Owner setup</h1><p>Configure the platform before public registration can be enabled.</p></div><div className="progress-count"><strong>{setupStatus?.completed_count || 0}<span>/{setupStatus?.required_count || 14}</span></strong><small>sections complete</small></div></div>
            <div className="setup-layout"><nav className="setup-nav" aria-label="Setup sections">{SETUP.map(item => { const Icon = item.icon; const done = setupStatus?.sections?.[item.id]?.complete; return <button key={item.id} className={`setup-step ${item.id === selectedSetup ? 'setup-step-active' : ''}`} onClick={() => chooseSetup(item)}><span className="step-icon">{done ? <Check /> : <Icon />}</span><span>{item.label}</span>{done && <BadgeCheck className="step-done" />}</button>; })}<button className={`setup-step ${selectedSetup === 'two-factor' ? 'setup-step-active' : ''}`} onClick={() => { setSelectedSetup('two-factor'); setError(''); }}><span className="step-icon"><ShieldCheck /></span><span>Two-factor authentication</span>{user.totp_enabled && <BadgeCheck className="step-done" />}</button></nav>
              <section className="setup-editor">{selectedSetup === 'two-factor' ? <><span className="eyebrow">ACCOUNT SECURITY</span><h2>Two-factor authentication</h2><p className="editor-intro">Protect the owner account with an authenticator app. Recovery codes are shown once.</p><div className="form-field"><label htmlFor="reauth-totp">Confirm owner password</label><input id="reauth-totp" type="password" autoComplete="current-password" value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} /></div>{user.totp_enabled ? <div className="confirmed-state"><ShieldCheck /><div><strong>2FA is enabled</strong><span>Your account requires an authenticator code at sign-in.</span></div></div> : !totp ? <button className="button-primary" disabled={busy || !reauthPassword} onClick={startTotp}><ShieldCheck />Set up authenticator</button> : <><div className="secret-box"><span>MANUAL SETUP KEY</span><code>{totp.secret}</code><p>Enter this key in your authenticator app, then enter the current 6-digit code.</p></div><form onSubmit={enableTotp}><div className="form-field"><label htmlFor="totp-code">Authenticator code</label><input id="totp-code" inputMode="numeric" autoComplete="one-time-code" value={totpCode} onChange={event => setTotpCode(event.target.value)} required /></div><button className="button-primary" disabled={busy || !reauthPassword}>Verify and enable <ArrowRight /></button></form></>}{recoveryCodes.length > 0 && <div className="recovery-box"><strong>Recovery codes · shown once</strong><div>{recoveryCodes.map(code => <code key={code}>{code}</code>)}</div><button className="button-secondary" onClick={() => setRecoveryCodes([])}>I stored these codes <Check /></button></div>}</> : <><span className="eyebrow">SETUP SECTION</span><h2>{activeSetup?.label}</h2><p className="editor-intro">Provide the required configuration values. Payment credentials and other secrets belong in your deployment secret manager, not here.</p><div className="required-fields"><span>REQUIRED FIELDS</span>{activeSetup?.fields.map(field => <code key={field}>{field}</code>)}</div><form onSubmit={saveSetup}><div className="form-field"><label htmlFor="setup-json">Configuration JSON</label><textarea id="setup-json" className="json-editor" spellCheck="false" value={configText} onChange={event => setConfigText(event.target.value)} /></div><div className="reauth-row"><KeyRound /><label htmlFor="reauth-config">Confirm owner password for sensitive changes</label><input id="reauth-config" type="password" autoComplete="current-password" value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} required /></div><button className="button-primary" disabled={busy}><Save />Save section</button></form></>}</section>
            </div>
            <section className="publish-bar"><div><strong>{status?.published ? 'Platform configuration is published' : 'Public registration remains disabled'}</strong><span>{setupStatus?.can_publish ? 'Required setup is complete. Publishing configuration does not enable member registration.' : 'All required sections and owner 2FA must be complete before publishing.'}</span></div><input aria-label="Owner password to publish" type="password" autoComplete="current-password" placeholder="Confirm owner password" value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} /><button className="button-publish" disabled={busy || !setupStatus?.can_publish || status?.published || !reauthPassword} onClick={publishPlatform}>{status?.published ? 'PUBLISHED' : 'PUBLISH PLATFORM'} {!status?.published && <ArrowRight />}</button></section>
          </>}

          {section === 'admins' && <><div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / ACCESS CONTROL</span><h1>Administrators</h1><p>Individual accounts with only the permissions assigned here. Owner access is separate.</p></div><span className="security-pill"><Users />{admins.length} / 5 ADMIN ACCOUNTS</span></div><section className="data-section"><div className="section-heading"><div><span className="eyebrow">ADMIN DIRECTORY</span><h2>Additional administrators</h2></div><span className="subtle-label">OWNER ACCOUNT EXCLUDED</span></div>{admins.length === 0 && <div className="empty-state">No administrator accounts have been created.</div>}{admins.map(admin => <div className="admin-row" key={admin.user_id}><div className="admin-ident"><span className="admin-avatar">{admin.display_name.slice(0, 1).toUpperCase()}</span><span><strong>{admin.display_name}</strong><small>{admin.email}</small></span></div><span className="admin-slot">ADMIN {admin.slot}</span><div className="permission-tags">{admin.permissions.map(permission => <code key={permission}>{permission}</code>)}</div><span className="admin-status">{admin.is_active ? 'ACTIVE' : 'DISABLED'}</span></div>)}</section>{admins.length < 5 && <section className="data-section admin-create"><div className="section-heading"><div><span className="eyebrow">NEW ACCOUNT</span><h2>Create administrator</h2></div></div><form onSubmit={createAdmin}><div className="admin-form-grid"><div className="form-field"><label htmlFor="admin-name">Name</label><input id="admin-name" autoComplete="off" value={adminForm.display_name} onChange={event => setAdminForm({ ...adminForm, display_name: event.target.value })} required /></div><div className="form-field"><label htmlFor="admin-email">Email</label><input id="admin-email" type="email" autoComplete="off" value={adminForm.email} onChange={event => setAdminForm({ ...adminForm, email: event.target.value })} required /></div><div className="form-field"><label htmlFor="admin-password">Initial password</label><input id="admin-password" type="password" autoComplete="new-password" minLength="12" value={adminForm.password} onChange={event => setAdminForm({ ...adminForm, password: event.target.value })} required /><small>12+ characters, upper/lowercase, number and symbol.</small></div></div><fieldset className="permission-fieldset"><legend>Assigned permissions</legend><div className="permission-grid">{ADMIN_PERMISSIONS.map(([permission, label]) => <label key={permission}><input type="checkbox" checked={adminForm.permissions.includes(permission)} onChange={event => setAdminForm({ ...adminForm, permissions: event.target.checked ? [...adminForm.permissions, permission] : adminForm.permissions.filter(item => item !== permission) })} /><span>{label}</span></label>)}</div></fieldset><div className="reauth-row"><KeyRound /><label htmlFor="admin-reauth">Confirm owner password</label><input id="admin-reauth" type="password" autoComplete="current-password" value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} required /></div><button className="button-primary" disabled={busy || adminForm.permissions.length === 0}><Users />Create administrator account</button></form></section>}</>}

          {section === 'security' && <><div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / ACCESS</span><h1>Security & sessions</h1><p>Review active sign-ins and revoke sessions you no longer recognize.</p></div><span className={`security-pill ${user.totp_enabled ? 'security-on' : ''}`}><ShieldCheck />{user.totp_enabled ? '2FA ENABLED' : '2FA REQUIRED'}</span></div><section className="data-section"><div className="section-heading"><div><span className="eyebrow">DEVICE MANAGEMENT</span><h2>Active sessions</h2></div><span className="subtle-label">{sessions.length} ACTIVE</span></div>{sessions.map(session => <div className="table-row" key={session.id}><div className="session-device"><LockKeyhole /><div><strong>{session.user_agent || 'Unknown device'}</strong><span>{session.ip_address || 'IP unavailable'} · signed in {new Date(session.created_at).toLocaleString()}</span></div></div><span className="session-current">{session.current ? 'CURRENT SESSION' : 'ACTIVE'}</span>{!session.current && <button className="text-danger" onClick={() => revokeSession(session.id)}>Revoke</button>}</div>)}</section><section className="data-section"><div className="section-heading"><div><span className="eyebrow">OWNER ACCOUNT</span><h2>Authentication controls</h2></div></div><div className="security-summary"><div><ShieldCheck /><span><strong>Password</strong><small>Argon2id password hash. Passwords are never stored in readable form.</small></span></div><div><Fingerprint /><span><strong>Two-factor authentication</strong><small>{user.totp_enabled ? 'Authenticator and recovery codes enabled.' : 'Set up an authenticator before publishing the platform.'}</small></span><button className="text-button" onClick={() => { setSelectedSetup('two-factor'); setSection('setup'); }}>Configure <ArrowRight /></button></div></div></section></>}

          {section === 'audit' && <><div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / SECURITY</span><h1>Audit trail</h1><p>Recorded authentication and platform configuration events.</p></div><span className="subtle-label">APPEND-ONLY API</span></div><section className="data-section audit-list">{auditRows.map(row => <div className="audit-row" key={row.id}><span className="audit-marker" /><div><strong>{row.event_type}</strong><span>{row.details && Object.keys(row.details).length ? JSON.stringify(row.details) : 'No additional details'}</span></div><time>{new Date(row.created_at).toLocaleString()}</time></div>)}</section></>}

          {section === 'health' && <><div className="page-heading"><div><span className="eyebrow">OWNER CONSOLE / OPERATIONS</span><h1>System health</h1><p>Unavailable integrations are identified explicitly; no market data is simulated.</p></div><span className="security-pill"><CircleHelp />SAFE MODE</span></div><div className="risk-banner"><AlertTriangle /><p>Market-dependent analysis remains unavailable until a verified data provider is configured. No prices, backtest results, or setup scores are displayed.</p></div><div className="service-grid health-grid">{systemServices.map(item => { const Icon = item.icon; return <div className="service-row" key={item.name}><span className="service-icon"><Icon /></span><div className="service-copy"><strong>{item.name}</strong><span>{item.state === 'healthy' ? 'Health check responding' : 'Provider or deployment configuration required'}</span></div><span className={`service-state state-${item.state}`}>{item.value}</span></div>; })}</div><div className="unconfigured-note"><Shield /><div><strong>Analysis proposals are not available</strong><span>Safe mode remains active because market data, the analysis engine, and risk engine are not configured.</span></div></div></>}
        </main>
        <footer className="risk-footer"><span>DRAGONFORGE · OWNER CONSOLE</span><span>ANALYSIS AND DECISION SUPPORT ONLY · NO TRADE EXECUTION</span></footer>
      </div>
    </div>
  );
}

function AdminConsole({ user, access, logout }) {
  return <main className="admin-console"><header className="admin-topbar"><div className="brand-lockup"><DragonMark /><div><strong>DRAGONFORGE</strong><span>ADMIN WORKSPACE</span></div></div><button className="logout-button" onClick={logout}><LogOut /> Sign out</button></header><div className="admin-content"><span className="eyebrow">ADMIN CONSOLE / LIMITED ACCESS</span><h1>Welcome, {user.display_name}</h1><p className="admin-intro">This individual account has only its assigned permissions. Owner credentials, private user data, and protected strategy settings are not available here.</p><div className="risk-banner"><AlertTriangle /><p>Market data and operational modules are not configured. No analysis, account information, or execution tools are available.</p></div><section className="data-section"><div className="section-heading"><div><span className="eyebrow">YOUR ACCESS</span><h2>Assigned permissions</h2></div></div>{(access?.permissions || []).map(permission => <div className="admin-permission" key={permission}><ShieldCheck /><code>{permission}</code></div>)}{!access?.permissions?.length && <div className="empty-state">No permissions have been assigned to this account.</div>}</section><div className="unconfigured-note"><CircleHelp /><div><strong>Admin workflows are not configured</strong><span>Application review, user support, and security alert actions will become available when their Phase 1 workflows are implemented.</span></div></div><div className="risk-notice">{RISK_NOTICE}</div></div></main>;
}

function AuthScreen({ mode, setMode, form, setForm, submit, busy, error, status }) {
  const bootstrap = mode === 'bootstrap';
  return <main className="auth-page"><section className="auth-aside"><div className="auth-brand"><DragonMark /><div><strong>DRAGONFORGE</strong><span>MARKET INTELLIGENCE</span></div></div><div className="auth-aside-copy"><span className="eyebrow">INDEPENDENT MARKET RESEARCH</span><h1>Evidence before conviction.</h1><p>A secure research workstation for market analysis, risk assessment, and decision support.</p></div><div className="auth-aside-bottom"><ShieldCheck /><span>Private by design. Owner-controlled. No trade execution.</span></div></section><section className="auth-main"><div className="auth-panel"><span className="eyebrow">OWNER BOOTSTRAP / PHASE 1</span><h2>{bootstrap ? 'Register platform owner' : 'Owner sign in'}</h2><p>{bootstrap ? 'The first account becomes the sole owner. Enter the one-time bootstrap token provisioned by the platform operator.' : 'Sign in to continue to the owner console.'}</p>{error && <div className="inline-alert" role="alert"><AlertTriangle />{error}</div>}<form onSubmit={submit}>{bootstrap && <div className="form-field"><label htmlFor="bootstrap-token">Owner bootstrap token</label><input id="bootstrap-token" type="password" autoComplete="off" value={form.bootstrap_token} onChange={event => setForm({ ...form, bootstrap_token: event.target.value })} required /><small>The token is configured in the deployment environment and is never stored with your account.</small></div>}{bootstrap && <div className="form-field"><label htmlFor="owner-name">Owner name</label><input id="owner-name" autoComplete="name" value={form.display_name} onChange={event => setForm({ ...form, display_name: event.target.value })} required /></div>}<div className="form-field"><label htmlFor="owner-email">Email address</label><input id="owner-email" type="email" autoComplete="username" value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} required /></div><div className="form-field"><label htmlFor="owner-password">Password</label><input id="owner-password" type="password" autoComplete={bootstrap ? 'new-password' : 'current-password'} minLength={bootstrap ? 12 : undefined} value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} required /><small>{bootstrap ? '12+ characters, uppercase and lowercase letters, number and symbol.' : 'Your password is protected with Argon2id hashing.'}</small></div>{!bootstrap && <div className="form-field"><label htmlFor="owner-totp">Authenticator or recovery code</label><input id="owner-totp" autoComplete="one-time-code" value={form.totp_code} onChange={event => setForm({ ...form, totp_code: event.target.value })} /><small>Leave empty if two-factor authentication is not enabled yet.</small></div>}<button className="button-primary auth-submit" disabled={busy}>{busy ? 'Please wait…' : bootstrap ? 'Create owner account' : 'Sign in'}<ArrowRight /></button></form>{bootstrap ? <div className="auth-state"><LockKeyhole />BOOTSTRAP AVAILABLE · OWNER ONLY</div> : !status?.owner_registered && <button className="text-button" onClick={() => setMode('bootstrap')}>Begin owner setup</button>}<div className="risk-notice">{RISK_NOTICE}</div></div></section></main>;
}

function DragonMark() {
  return <div className="dragon-mark" aria-hidden="true"><span>DF</span></div>;
}