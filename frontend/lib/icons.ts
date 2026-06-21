const CLASS_ICON: Record<string, string> = {
  vehicle: "/icons/vehicle.svg",
  ship: "/icons/ship.svg",
  aircraft: "/icons/aircraft.svg",
  plane: "/icons/aircraft.svg",
  helicopter: "/icons/helicopter.svg",
  tank: "/icons/vehicle.svg",
  "large-vehicle": "/icons/vehicle.svg",
  "small-vehicle": "/icons/vehicle.svg",
};

export function iconForClass(className: string): string {
  return CLASS_ICON[className.toLowerCase()] || "/icons/vehicle.svg";
}

export function scaleForConfidence(confidence: number): number {
  return 0.6 + confidence * 0.8;
}

export const CHANGE_COLORS: Record<string, string> = {
  appeared: "#98c379",
  disappeared: "#e06c75",
  moved: "#e5c07b",
};

export function coverageColor(hoursAgo: number): string {
  if (hoursAgo < 6) return "rgba(152, 195, 121, 0.35)";
  if (hoursAgo < 48) return "rgba(229, 192, 123, 0.35)";
  return "rgba(224, 108, 117, 0.35)";
}
