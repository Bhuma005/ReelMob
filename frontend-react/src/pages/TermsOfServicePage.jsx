import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { FileText, ExternalLink, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function TermsOfServicePage() {
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
          <FileText className="w-8 h-8 text-accent" />
          Terms of Service
        </h1>
        <p className="text-xs text-text-muted font-mono">
          Last updated: October 12, 2026 • Effective Date: October 12, 2026
        </p>
      </div>

      <Card className="bg-surface border-border p-6 space-y-6 leading-relaxed text-sm text-text-muted">
        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">1. Acceptance of Terms</h2>
          <p>
            By accessing or using ReelMob ("the service"), you agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use the application.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">2. Description of Service</h2>
          <p>
            ReelMob provides intelligent video processing, vertical re-framing (9:16 aspect ratio), metadata analysis, and scheduling automation for publishing short-form video content to YouTube Shorts and connected social media channels.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">3. YouTube Terms of Service & Third-Party Platforms</h2>
          <p>
            ReelMob connects to third-party APIs including YouTube API Services. By connecting your YouTube account to ReelMob, you explicitly acknowledge and agree to comply with the{' '}
            <a 
              href="https://www.youtube.com/t/terms" 
              target="_blank" 
              rel="noreferrer" 
              className="text-accent underline inline-flex items-center gap-1"
            >
              YouTube Terms of Service <ExternalLink className="w-3 h-3" />
            </a>.
          </p>
          <p>
            You are solely responsible for ensuring that all video content uploaded through ReelMob adheres to YouTube’s Community Guidelines and copyright policies.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">4. User Content & Intellectual Property</h2>
          <p>
            You retain all ownership and intellectual property rights to the videos, images, titles, and descriptions you upload and publish through ReelMob. ReelMob does not claim ownership over any user content. You represent that you hold all necessary rights and licenses for the media you process through the platform.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">5. Prohibited Uses</h2>
          <p>You agree not to use ReelMob to:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Upload or distribute content that violates third-party copyright, trademark, or intellectual property rights.</li>
            <li>Post spam, malware, phishing links, or misleading metadata.</li>
            <li>Exceed or circumvent YouTube Data API quota and rate limits artificially.</li>
            <li>Interfere with or disrupt the security or integrity of ReelMob cloud infrastructure.</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">6. Limitation of Liability & Disclaimers</h2>
          <p>
            ReelMob is provided on an "as is" and "as available" basis without warranties of any kind. We are not liable for any account restrictions, video removals, or algorithmic performance changes imposed by third-party platforms (including YouTube or Google).
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">7. Termination</h2>
          <p>
            You may stop using ReelMob at any time by disconnecting your channel and ceasing use of the application. We reserve the right to suspend or terminate access to the service for violations of these Terms.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-bold text-text uppercase tracking-wide">8. Contact Information</h2>
          <p>
            If you have questions regarding these Terms of Service, please contact:
          </p>
          <p className="font-mono text-accent">
            Email: bhumanreddy492@gmail.com
          </p>
        </section>
      </Card>
    </div>
  );
}
