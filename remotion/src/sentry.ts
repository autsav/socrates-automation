import * as Sentry from "@sentry/react";

const dsn = process.env.REACT_APP_SENTRY_DSN || process.env.SENTRY_DSN || "";

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.REACT_APP_SENTRY_ENVIRONMENT || process.env.SENTRY_ENVIRONMENT || "development",
    release: process.env.REACT_APP_SENTRY_RELEASE || process.env.SENTRY_RELEASE || "unknown",
    // 10% transaction sampling keeps costs low while still surfacing perf issues.
    tracesSampleRate: Number(process.env.REACT_APP_SENTRY_TRACES_SAMPLE_RATE || process.env.SENTRY_TRACES_SAMPLE_RATE || "0.1"),
    // Capture React render errors and component stack.
    integrations: [Sentry.replayIntegration()],
    replaysSessionSampleRate: 0.0,
    replaysOnErrorSampleRate: 1.0,
  });
}

export { Sentry };
