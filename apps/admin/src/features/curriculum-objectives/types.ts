import type { CanonicalProgram } from "@equiped/types";

export interface Objective {
  objective_id: string;
  code: string;
  description: string;
  program: CanonicalProgram;
  version: number;
  mapping_count: number;
}
export interface ObjectiveInput {
  code: string;
  description: string;
  program: CanonicalProgram;
  version?: number;
}
export interface Course {
  course_id: string;
  course_code: string;
  course_title: string;
  program: string;
}
export type Level = "I" | "E" | "D";
export interface Mappings {
  course_id: string;
  version: number;
  entries: { objective_id: string; level: Level }[];
}
