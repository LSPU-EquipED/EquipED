import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useBlocker } from "@tanstack/react-router";
import { curriculumApi } from "./api";
import type { Mappings, ObjectiveInput } from "./types";

const key = ["adminCurriculum"];
export function useObjectives() {
  return useQuery({
    queryKey: [...key, "objectives"],
    queryFn: curriculumApi.objectives,
    refetchOnWindowFocus: false,
  });
}
export function useCourses() {
  return useQuery({
    queryKey: [...key, "courses"],
    queryFn: curriculumApi.courses,
  });
}
export function useMappings(id: string) {
  return useQuery({
    queryKey: [...key, "mappings", id],
    queryFn: () => curriculumApi.mappings(id),
    enabled: !!id,
    refetchOnWindowFocus: false,
  });
}
export function useSaveObjective(id?: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: ObjectiveInput) => curriculumApi.saveObjective(data, id),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
export function useSaveMappings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data: Mappings) => curriculumApi.saveMappings(data),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}
export function useUnsavedChanges(dirty: boolean) {
  useBlocker({
    shouldBlockFn: () =>
      dirty && !window.confirm("Discard your unsaved curriculum changes?"),
    enableBeforeUnload: dirty,
  });
}
