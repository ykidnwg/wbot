import { DevelopmentStatus } from "@/components/development-status";

export default function AnalyticsPage() {
  return <DevelopmentStatus title="Analitik" status="Belum tersedia" description="Belum ada analytics adapter resmi yang dikonfigurasi. Metrik eksternal seperti reach, impressions, clicks, dan revenue ditandai unavailable sampai sumber API terhubung." />;
}
