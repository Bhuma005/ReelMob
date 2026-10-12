import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { ShieldCheck, Lock, ExternalLink, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-20 pt-4">
      <div className="flex items-center gap-2 mb-2">
        <Link 
          to="/" 
          className="text-xs text-text-muted hover:text-accent flex items-center gap-1 font-mono transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </Link>
      </div>

      <div className="space-y-1">
        <h1 className="text-3xl font-black uppercase tracking-tight text-text flex items-center gap-3">
          <ShieldCheck className="w-8 h-8 text-accent" />
          Privacy Policy
        </h1>
        <p className="text-xs text-text-muted font-mono">
          Last updated: October 12, 2026 • Effective Date: October 12, 2026
        </p>
      </div>

      <Card className="bg-surface border-border p-6 space-y-6 leading-relaxed text-sm text-text-muted">
        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">1. Overview</h2>
          <p>
            ReelMob ("we", "our", or "the platform") is an automated short-form video optimization, intelligence, and cloud publishing tool. This Privacy Policy outlines how ReelMob handles, stores, and protects information when you use our service, with particular focus on YouTube API Services integration.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">2. Google & YouTube API Services</h2>
          <p>
            ReelMob uses YouTube API Services to allow you to publish video content (YouTube Shorts) directly to your authenticated YouTube channel. By using ReelMob to upload content to YouTube, you agree to the{' '}
            <a 
              href="https://www.youtube.com/t/terms" 
              target="_blank" 
              rel="noreferrer" 
              className="text-accent underline inline-flex items-center gap-1"
            >
              YouTube Terms of Service <ExternalLink className="w-3 h-3" />
            </a>{' '}
            and the{' '}
            <a 
              href="https://policies.google.com/privacy" 
              target="_blank" 
              rel="noreferrer" 
              className="text-accent underline inline-flex items-center gap-1"
            >
              Google Privacy Policy <ExternalLink className="w-3 h-3" />
            </a>.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">3. Information We Collect and Access</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              <strong className="text-text">Google Account & YouTube Channel Data:</strong> When you connect your YouTube channel via Google OAuth, we access your channel title, channel ID, and OAuth access/refresh tokens strictly for the purpose of uploading videos requested by you.
            </li>
            <li>
              <strong className="text-text">Video Files and Metadata:</strong> Videos, titles, descriptions, and hashtags you submit for optimization and scheduling.
            </li>
            <li>
              <strong className="text-text">We Do Not Collect Personal Sensitive Data:</strong> We do not collect your personal browsing history, passwords, or personal identity documents.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">4. How We Use Information</h2>
          <p>ReelMob uses collected data exclusively to:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Authenticate your YouTube account using OAuth 2.0.</li>
            <li>Upload and publish YouTube Shorts to your connected channel at your designated schedule or on-demand.</li>
            <li>Provide algorithm engagement recommendations and title/description generation.</li>
          </ul>
          <p className="mt-2 text-xs bg-surface-elevated/80 border border-border p-3 rounded-lg text-text">
            <strong>Google API Services User Data Policy Compliance:</strong> ReelMob’s use and transfer of information received from Google APIs to any other app will adhere to the{' '}
            <a 
              href="https://developers.google.com/terms/api-services-user-data-policy" 
              target="_blank" 
              rel="noreferrer" 
              className="text-accent underline"
            >
              Google API Services User Data Policy
            </a>
            , including the Limited Use requirements.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">5. Data Sharing and Third Parties</h2>
          <p>
            ReelMob <strong className="text-text">does not sell, rent, trade, or transfer</strong> your personal data or Google user data to any external third parties or advertising networks. Video processing is executed via our isolated secure cloud infrastructure.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">6. Token Storage & Security</h2>
          <p>
            OAuth refresh tokens and credentials are encrypted and stored in PostgreSQL with Row Level Security (RLS) enabled. We employ industry-standard encryption protocols (TLS/SSL) for all network communication between your browser, our servers, and Google APIs.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">7. Revoking Access & Data Deletion</h2>
          <p>
            You can revoke ReelMob’s access to your YouTube channel at any time either by:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>
              Clicking <strong>Disconnect YouTube</strong> in ReelMob under the <strong>Connections</strong> tab.
            </li>
            <li>
              Visiting the{' '}
              <a 
                href="https://myaccount.google.com/permissions" 
                target="_blank" 
                rel="noreferrer" 
                className="text-accent underline inline-flex items-center gap-1"
              >
                Google Security Settings Permissions Page <ExternalLink className="w-3 h-3" />
              </a>{' '}
              and removing permissions for ReelMob.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">8. Contact Us</h2>
          <p>
            If you have questions or concerns regarding this Privacy Policy or ReelMob's data practices, please contact us at:
          </p>
          <p className="font-mono text-accent">
            Email: bhumanreddy492@gmail.com
          </p>
        </section>
      </Card>
    </div>
  );
}
