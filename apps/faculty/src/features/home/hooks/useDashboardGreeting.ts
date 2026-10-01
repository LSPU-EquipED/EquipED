import { useEffect, useState } from "react";
import { formatDashboardGreeting } from "../utils/dashboardGreeting";

export function useDashboardGreeting(displayName?: string | null) {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const updateTime = () => setNow(new Date());
    const interval = window.setInterval(updateTime, 60_000);
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") updateTime();
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  return formatDashboardGreeting(now, displayName);
}
