import { describe, expect, it } from "vitest";
import {
  mapStatusToApi,
  formatFileSize,
  type StorageStatusFilter,
} from "../storage.utils";

describe("storage.utils", () => {
  describe("mapStatusToApi", () => {
    it("maps PROCESSED to ready", () => {
      expect(mapStatusToApi("PROCESSED")).toBe("ready");
    });

    it("maps PROCESSING to processing", () => {
      expect(mapStatusToApi("PROCESSING")).toBe("processing");
    });

    it("maps FAILED to failed", () => {
      expect(mapStatusToApi("FAILED")).toBe("failed");
    });

    it("maps all and invalid values to undefined", () => {
      expect(mapStatusToApi("all")).toBeUndefined();
      expect(mapStatusToApi("unknown" as StorageStatusFilter)).toBeUndefined();
    });
  });

  describe("formatFileSize", () => {
    it("formats file sizes accurately", () => {
      expect(formatFileSize(500)).toBe("500 B");
      expect(formatFileSize(2048)).toBe("2.0 KB");
      expect(formatFileSize(15.5 * 1024 * 1024)).toBe("15.50 MB");
    });
  });
});
