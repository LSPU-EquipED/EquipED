/** Institutional printed names supplied for the approval sheet. These are not
 * signature or approval records. Keep college-specific appointments scoped. */
export const APPROVAL_SHEET_SIGNATORIES = {
  chairperson: 'Maida O. Sarmiento',
  director: 'Dr. Elaine Rose G. Nachon',
  vicePresident: 'Atty. Rushid Jay S. Sancon',
  deansByCollege: { CCS: 'DR. MIA V. VILLARICA' } as Record<string, string>,
} as const;
