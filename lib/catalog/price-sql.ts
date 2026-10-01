/**
 * P116 — SQL twin of lib/catalog/queries `currentOfficialPrice`.
 *
 * The Prisma predicate is the single accepted contract for public price
 * surfaces:
 *   isCurrent + SourceDocument VERIFIED + Source ACTIVE + official sourceType
 *   + BrochureVerification VERIFIED
 * Raw-SQL routes (models / compare / vehicle detail) MUST use this helper so
 * no surface can re-introduce a weaker predicate (secondary, inactive or
 * unverified documents can never be shown as official prices).
 *
 * Aliases inside are prefixed `op*` so they never collide with route aliases.
 */
export const OFFICIAL_SOURCE_TYPES_SQL =
  `('OFFICIAL_MANUFACTURER','OFFICIAL_MANUFACTURER_BROCHURE','OFFICIAL_MANUFACTURER_PRICE_LIST','OFFICIAL_MANUFACTURER_PRESS_RELEASE')`;

/** EXISTS guard for <priceAlias>'s source document passing the full chain. */
export function currentOfficialPriceSql(priceAlias: string): string {
  return (
    `EXISTS (SELECT 1 FROM "SourceDocument" opsd ` +
    `JOIN "Source" ops ON ops.id = opsd."sourceId" ` +
    `WHERE opsd.id = ${priceAlias}."sourceDocumentId" ` +
    `AND opsd.status = 'VERIFIED' ` +
    `AND ops.status = 'ACTIVE' ` +
    `AND ops."sourceType" IN ${OFFICIAL_SOURCE_TYPES_SQL} ` +
    `AND EXISTS (SELECT 1 FROM "BrochureVerification" opbv ` +
    `WHERE opbv."sourceDocumentId" = opsd.id AND opbv.status = 'VERIFIED'))`
  );
}

/** Full price-row predicate: isCurrent + non-null doc + full document chain. */
export function currentOfficialPriceWhere(priceAlias: string): string {
  return (
    `${priceAlias}."isCurrent" = true ` +
    `AND ${priceAlias}."sourceDocumentId" IS NOT NULL ` +
    `AND ${currentOfficialPriceSql(priceAlias)}`
  );
}
