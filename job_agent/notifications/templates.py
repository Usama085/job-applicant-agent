"""HTML email templates for notifications and reports."""

from __future__ import annotations

from datetime import datetime


def daily_summary_html(
    date: str,
    applications: list[dict],
    stats: dict,
) -> str:
    """Generate HTML for the daily summary email."""
    rows = ""
    for app in applications:
        status = app.get("status", "Unknown")
        status_color = {
            "Applied": "#28a745",
            "Failed": "#dc3545",
            "Manual Intervention Required": "#ffc107",
            "Skipped": "#6c757d",
            "Duplicate": "#6c757d",
        }.get(status, "#333")

        rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">{app.get('title', 'N/A')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{app.get('company', 'N/A')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{app.get('location', 'N/A')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{app.get('platform', 'N/A').title()}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">{app.get('applied_at', 'N/A')[:19]}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <a href="{app.get('job_url', '#')}" style="color:#0066cc;">Link</a>
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                <span style="color:{status_color};font-weight:bold;">{status}</span>
            </td>
        </tr>"""

    if not rows:
        rows = """
        <tr>
            <td colspan="7" style="padding:20px;text-align:center;color:#666;">
                No applications were made today.
            </td>
        </tr>"""

    total = stats.get("total", len(applications))
    applied = stats.get("applied", 0)
    failed = stats.get("failed", 0)
    manual = stats.get("manual", 0)
    skipped = stats.get("skipped", 0)

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;">
        <h2 style="color:#333;border-bottom:2px solid #0066cc;padding-bottom:10px;">
            Job Application Agent - Daily Report
        </h2>
        <p style="color:#666;">Date: {date}</p>

        <div style="display:flex;gap:15px;margin:20px 0;">
            <div style="background:#e8f5e9;padding:15px;border-radius:8px;flex:1;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#28a745;">{applied}</div>
                <div style="color:#666;font-size:12px;">Applied</div>
            </div>
            <div style="background:#fce4ec;padding:15px;border-radius:8px;flex:1;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#dc3545;">{failed}</div>
                <div style="color:#666;font-size:12px;">Failed</div>
            </div>
            <div style="background:#fff3e0;padding:15px;border-radius:8px;flex:1;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#ffc107;">{manual}</div>
                <div style="color:#666;font-size:12px;">Manual</div>
            </div>
            <div style="background:#f5f5f5;padding:15px;border-radius:8px;flex:1;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#6c757d;">{skipped}</div>
                <div style="color:#666;font-size:12px;">Skipped</div>
            </div>
            <div style="background:#e3f2fd;padding:15px;border-radius:8px;flex:1;text-align:center;">
                <div style="font-size:24px;font-weight:bold;color:#0066cc;">{total}</div>
                <div style="color:#666;font-size:12px;">Total</div>
            </div>
        </div>

        <table style="width:100%;border-collapse:collapse;margin-top:20px;">
            <thead>
                <tr style="background:#f8f9fa;">
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Job Title</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Company</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Location</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Platform</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Time</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Link</th>
                    <th style="padding:10px;text-align:left;border-bottom:2px solid #dee2e6;">Status</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <p style="margin-top:30px;color:#999;font-size:12px;border-top:1px solid #eee;padding-top:10px;">
            AI Job Application Agent v1.0.0 | Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """


def captcha_alert_html(
    platform: str,
    job_url: str,
    captcha_type: str,
    job_title: str,
    company: str,
) -> str:
    """Generate HTML for an immediate CAPTCHA alert email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#dc3545;">Manual Intervention Required</h2>

        <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:20px;margin:20px 0;">
            <p style="margin:0 0 10px;"><strong>Platform:</strong> {platform.title()}</p>
            <p style="margin:0 0 10px;"><strong>Job:</strong> {job_title} at {company}</p>
            <p style="margin:0 0 10px;"><strong>Reason:</strong> {captcha_type.replace('_', ' ').title()} detected</p>
            <p style="margin:0;">
                <strong>Link:</strong>
                <a href="{job_url}" style="color:#0066cc;">{job_url}</a>
            </p>
        </div>

        <p>The agent could not complete this application automatically.
        Please open the link above and complete the verification manually.</p>

        <p style="color:#999;font-size:12px;margin-top:20px;">
            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """


def login_expired_html(platform: str) -> str:
    """Generate HTML for a login expired alert email."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
        <h2 style="color:#dc3545;">Login Session Expired</h2>

        <div style="background:#f8d7da;border:1px solid #f5c6cb;border-radius:8px;padding:20px;margin:20px 0;">
            <p><strong>Platform:</strong> {platform.title()}</p>
            <p>Your {platform.title()} session has expired. The agent cannot
            apply to jobs on this platform until you re-login.</p>
        </div>

        <h3>To fix this:</h3>
        <ol>
            <li>Open a terminal in the project directory</li>
            <li>Run: <code>python scripts/manual_login.py {platform}</code></li>
            <li>Log in to {platform.title()} in the browser that opens</li>
            <li>Press Enter in the terminal to save the session</li>
        </ol>

        <p style="color:#999;font-size:12px;margin-top:20px;">
            {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """
