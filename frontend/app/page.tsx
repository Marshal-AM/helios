"use client";

import dynamic from "next/dynamic";

const GlobeDashboard = dynamic(() => import("@/components/globe/GlobeDashboard"), {
  ssr: false,
  loading: () => <div className="auth-loading">Loading 3D globe…</div>,
});

export default function HomePage() {
  return <GlobeDashboard />;
}
