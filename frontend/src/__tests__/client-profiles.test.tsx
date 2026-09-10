/**
 * Client Profiles — the rules that a plausible-looking implementation gets
 * wrong.
 *
 * Asserted by rendering to static markup (`react-dom/server`), which is the
 * house method: the locked stack adds no DOM testing library, and browser-level
 * workflow is Playwright's job (Step 39, Step 54).
 *
 * Four things are pinned, and each one is a requirement the owner stated as a
 * prohibition rather than a feature:
 *
 * 1. **ONE document list, never folders by type.** Six types render as six rows
 *    of one table, and the type appears as a chip in a column. This is the
 *    structural version of "do not create MSA/NDA/SLA sections".
 * 2. **The three version roles stay three.** A client's redline is not the
 *    signed copy, and an undeclared version says nothing rather than guessing.
 * 3. **Absence reads as absence.** An unknown field says "Not available", never
 *    a dash that looks checked — the rendering half of rule 21's discipline.
 * 4. **A client's own status carries no legal colour.** It is a filing state,
 *    and DESIGN.md forbids two axes sharing a visual channel.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import type { ClientContract, Counterparty, DocumentVersion } from "@/lib/types";

// Everything below renders one presentational component. `useSession` is the
// only ambient dependency they have, and a permissive `can` is the right stub:
// these tests are about WHAT is rendered, and the permission gating has its own
// coverage in `permissions.test.tsx` and server-side in `test_rbac_personas.py`.
vi.mock("@/lib/session", () => ({
  useSession: () => ({ can: () => true, identity: { user_id: "u1" } }),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

import { ClientAvatar, ClientStatus, Fact, websiteHref } from "@/components/clients/ClientBits";
import { ClientDocuments } from "@/components/clients/ClientDocuments";
import { ClientDetails } from "@/components/clients/ClientTabs";
import { nameKey } from "@/components/clients/ClientForm";
import {
  activityWords,
  clientCountLabel,
  currentVersion,
  hasProfileDetail,
  mergeProfile,
  signedVersion,
  typesPresent,
  versionCountLabel,
} from "@/components/clients/model";
import {
  clientLocation,
  companyInitials,
  documentTypeChip,
  documentTypeLabel,
  versionRoleLabel,
} from "@/lib/documentTypes";

function version(over: Partial<DocumentVersion> = {}): DocumentVersion {
  return {
    id: "v1", contract_id: "c1", version_number: 1,
    original_filename: "msa.pdf", mime_type: "application/pdf",
    file_size_bytes: 1024, file_hash: "h", processing_status: "COMPLETED",
    extraction_status: "COMPLETED", uploaded_by: "u1",
    created_at: "2026-08-12T00:00:00Z",
    ...over,
  } as DocumentVersion;
}

function doc(over: Partial<ClientContract> = {}): ClientContract {
  return {
    id: "c1", owner_id: "u1", name: "Master Services Agreement",
    contract_type: "MSA", status: "ACTIVE", archived_at: null,
    created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-12T00:00:00Z",
    versions: [version()], version_count: 1, signed: false,
    ...over,
  } as ClientContract;
}

function client(over: Partial<Counterparty> = {}): Counterparty {
  return {
    id: "cp1", name: "Northwind Systems", status: "ACTIVE",
    created_at: "2026-07-01T00:00:00Z", updated_at: "2026-08-12T00:00:00Z",
    ...over,
  } as Counterparty;
}

// =====================================================================
// 1. ONE list, never folders
// =====================================================================
describe("the client's documents are one list, whatever the types are", () => {
  const SIX: ClientContract[] = [
    doc({ id: "c1", name: "Master Services Agreement", contract_type: "MSA" }),
    doc({ id: "c2", name: "Mutual NDA", contract_type: "NDA" }),
    doc({ id: "c3", name: "Service Level Agreement", contract_type: "SLA" }),
    doc({ id: "c4", name: "Amendment 1", contract_type: "AMENDMENT" }),
    doc({ id: "c5", name: "Order Form", contract_type: "ORDER_FORM" }),
    doc({ id: "c6", name: "Partner Agreement", contract_type: "OTHER" }),
  ];

  it("renders every type in ONE table and no per-type sections", () => {
    const html = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: SIX })} onChanged={() => {}} />,
    );

    // Every document is present, by name.
    for (const contract of SIX) {
      expect(html).toContain(contract.name);
    }
    // ONE table, and one heading — six type sections would be six of each.
    expect(html.match(/<table/g)?.length).toBe(1);
    expect(html.match(/<tbody/g)?.length).toBe(1);
    // And no per-type heading anywhere: the six codes appear as chips in a
    // column, never as a section title.
    for (const heading of ["<h3>MSA", "<h3>NDA", "<h3>SLA", ">MSA documents"]) {
      expect(html).not.toContain(heading);
    }
  });

  it("shows the type as a short word, never a raw code with an underscore", () => {
    /* The owner asked for "MSA / NDA / SLA / Amendment / PO / Other" — a chip a
     * reader parses at a glance. `ORDER_FORM` and `PRIVACY_POLICY` are wire
     * values, and an underscore in a table cell is a leaked identifier. */
    expect(documentTypeChip("MSA")).toBe("MSA");
    expect(documentTypeChip("NDA")).toBe("NDA");
    expect(documentTypeChip("ORDER_FORM")).toBe("Order form");
    expect(documentTypeChip("PRIVACY_POLICY")).toBe("Privacy");
    expect(documentTypeChip("AMENDMENT")).toBe("Amendment");
    expect(documentTypeChip(null)).toBeNull();
    // No chip anywhere carries an underscore.
    for (const type of ["MSA", "NDA", "TOS", "SLA", "DPA", "AUP",
                        "PRIVACY_POLICY", "ORDER_FORM", "AMENDMENT", "OTHER"]) {
      expect(documentTypeChip(type)).not.toContain("_");
    }
    // ...and the full label is still what the title says, so nothing is lost.
    expect(documentTypeLabel("ORDER_FORM")).toBe("Order Form");
  });

  it("renders the short chip in the cell and the full label as its title", () => {
    const html = renderToStaticMarkup(
      <ClientDocuments
        client={client({ contracts: [doc({ contract_type: "ORDER_FORM" })] })}
        onChanged={() => {}} />,
    );
    expect(html).toContain(">Order form<");
    expect(html).toContain('title="Order Form"');
    expect(html).not.toContain(">ORDER_FORM<");
  });

  it("shows document type as metadata in its own column", () => {
    const html = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: SIX })} onChanged={() => {}} />,
    );
    // The chip idiom the rest of the app uses for a type, once per document.
    expect(html.match(/ws-chip--type/g)?.length).toBe(SIX.length);
    // The full label is the chip's title, so "ORDER_FORM" is never the reader's
    // only clue to what the row is.
    expect(html).toContain("Order Form");
  });

  it("offers type as a FILTER only once there is more than one type", () => {
    const one = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: [SIX[0]!] })} onChanged={() => {}} />,
    );
    expect(one).not.toContain("All types");

    const many = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: SIX })} onChanged={() => {}} />,
    );
    expect(many).toContain("All types");
  });

  it("typesPresent is for a select, and returns a flat sorted list", () => {
    expect(typesPresent(SIX)).toEqual(
      ["AMENDMENT", "MSA", "NDA", "ORDER_FORM", "OTHER", "SLA"]);
    expect(typesPresent([])).toEqual([]);
  });

  it("says so plainly when a client has no documents", () => {
    const html = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: [] })} onChanged={() => {}} />,
    );
    expect(html).toContain("No legal documents for this client yet");
    expect(html).not.toContain("<table");
  });
});

// =====================================================================
// 2. Versions — three roles, and nothing overwritten
// =====================================================================
describe("document versions", () => {
  const NEGOTIATION = [
    version({ id: "v3", version_number: 3, version_role: "FINAL_SIGNED",
              created_at: "2026-08-25T00:00:00Z" }),
    version({ id: "v2", version_number: 2, version_role: "CLIENT_MODIFIED",
              created_at: "2026-08-15T00:00:00Z" }),
    version({ id: "v1", version_number: 1, version_role: "COMPANY_DRAFT",
              created_at: "2026-08-12T00:00:00Z" }),
  ];

  it("counts every version, so nothing reads as having been replaced", () => {
    const html = renderToStaticMarkup(
      <ClientDocuments
        client={client({ contracts: [doc({ versions: NEGOTIATION, signed: true })] })}
        onChanged={() => {}} />,
    );
    expect(html).toContain("3 versions");
    expect(versionCountLabel(1)).toBe("1 version");
  });

  it("keeps the three roles distinct, in the reader's own words", () => {
    expect(versionRoleLabel("COMPANY_DRAFT")).toBe("Company draft");
    expect(versionRoleLabel("CLIENT_MODIFIED")).toBe("Client modified");
    expect(versionRoleLabel("FINAL_SIGNED")).toBe("Final signed");
  });

  it("never treats the client's redline as the signed copy", () => {
    const redlined = [
      version({ id: "v2", version_number: 2, version_role: "CLIENT_MODIFIED" }),
      version({ id: "v1", version_number: 1, version_role: "COMPANY_DRAFT" }),
    ];
    // The newest version is the client's, and there is no signed one.
    expect(currentVersion(redlined)?.id).toBe("v2");
    expect(signedVersion(redlined)).toBeNull();
    // And when one exists it is found by its DECLARATION, not by being newest.
    expect(signedVersion(NEGOTIATION)?.id).toBe("v3");
  });

  it("the current version is the highest number, not the signed one", () => {
    // A signed v3 followed by a v4 the client sent back: the document is at v4,
    // and saying otherwise would hide where the negotiation actually stands.
    const reopened = [
      ...NEGOTIATION,
      version({ id: "v4", version_number: 4, version_role: "CLIENT_MODIFIED" }),
    ];
    expect(currentVersion(reopened)?.id).toBe("v4");
    expect(signedVersion(reopened)?.id).toBe("v3");
  });

  it("says nothing about a version nobody classified", () => {
    expect(versionRoleLabel(undefined)).toBeNull();
    expect(versionRoleLabel(null)).toBeNull();
    // No inference from the number, the filename or the date.
    expect(versionRoleLabel("v1")).toBeNull();
    expect(currentVersion([])).toBeNull();
    expect(currentVersion(undefined)).toBeNull();
  });
});

// =====================================================================
// 3. Absence reads as absence
// =====================================================================
describe("what is not known says so", () => {
  it("renders Not available, never a dash", () => {
    const html = renderToStaticMarkup(<Fact label="Website" value={undefined} />);
    expect(html).toContain("Not available");
    expect(html).not.toContain("—");
  });

  it("renders a value as itself, and a link where there is one", () => {
    const html = renderToStaticMarkup(
      <Fact label="Website" value="northwind.test"
            href={websiteHref("northwind.test")} />);
    expect(html).toContain("northwind.test");
    expect(html).toContain('href="https://northwind.test"');
  });

  it("does not rewrite a website the human already schemed", () => {
    expect(websiteHref("http://northwind.test")).toBe("http://northwind.test");
    expect(websiteHref("https://northwind.test")).toBe("https://northwind.test");
    expect(websiteHref(undefined)).toBeNull();
  });

  it("the Details tab shows every field, including the empty ones", () => {
    /* Unlike the compact header strip: the Details tab's job is precisely to
     * say what is and is not on record, so an absent field belongs there. */
    const html = renderToStaticMarkup(
      <ClientDetails client={client({ industry: "Information Technology" })} />);
    expect(html).toContain("Information Technology");
    expect(html).toContain("Registered name");
    expect(html).toContain("Not available");
  });

  it("the header strip is absent entirely when there is nothing in it", () => {
    /* Five "Not available" cells would be worse than no row. */
    expect(hasProfileDetail(client())).toBe(false);
    expect(hasProfileDetail(client({ website: "northwind.test" }))).toBe(true);
    expect(hasProfileDetail(client({ primary_contact_name: "A. Person" }))).toBe(true);
    // Industry alone does NOT bring the strip back: it is already in the
    // header line above it, and a strip holding one value and four blanks is
    // the thing this guard exists to prevent.
    expect(hasProfileDetail(client({ industry: "IT" }))).toBe(false);
  });

  it("a location is only as complete as what was recorded", () => {
    expect(clientLocation({ city: "Mumbai", state_region: "Maharashtra", country: "India" }))
      .toBe("Mumbai, Maharashtra, India");
    expect(clientLocation({ city: "Mumbai" })).toBe("Mumbai");
    expect(clientLocation({})).toBeNull();
  });
});

// =====================================================================
// 4. A client's status is not a legal state
// =====================================================================
describe("a client's status carries no legal colour", () => {
  it("always renders the word, never colour alone", () => {
    for (const [state, word] of [["ACTIVE", "Active"], ["PROSPECTIVE", "Prospective"],
                                 ["INACTIVE", "Inactive"]] as const) {
      const html = renderToStaticMarkup(<ClientStatus status={state} />);
      expect(html).toContain(word);
    }
  });

  it("a document row's Analyze is not a primary action", () => {
    /* One primary per view. Six primary buttons painted the table blue and
     * out-shouted the document names — Upload is the view's primary action. */
    const html = renderToStaticMarkup(
      <ClientDocuments client={client({ contracts: [doc(), doc({ id: "c2" })] })}
                       onChanged={() => {}} />);
    // Every row-action cell, and what is inside it.
    const cells = [...html.matchAll(/<td class="ws-cl__rowacts">(.*?)<\/td>/g)]
      .map((m) => m[1]!);
    expect(cells).toHaveLength(2);
    for (const cell of cells) {
      expect(cell).toContain("Analyze");
      expect(cell).not.toContain("ws-btn--primary");
    }
    // Upload, the view's one primary action, still is one.
    expect(html).toContain('class="ws-btn ws-btn--sm ws-btn--primary"');
  });

  it("never borrows a finding tone or a status-pill class", () => {
    /* DESIGN.md: "never let two axes share a visual channel". A client ACTIVE
     * must not wear the green that means "Acceptable", and must not reuse the
     * document bucket pill either. */
    const html = renderToStaticMarkup(<ClientStatus status="ACTIVE" />);
    for (const legal of ["ws-status-pill", "ws-findings-badge", "ws-chip--bucket",
                         "--ok", "--warn", "--bad", "tone-ok"]) {
      expect(html).not.toContain(legal);
    }
    expect(html).toContain("ws-cl__status--active");
  });
});

// =====================================================================
// Small things that carry a rule
// =====================================================================
describe("presentation helpers", () => {
  it("initials skip legal suffixes, so four Pvt Ltds are not all PL", () => {
    expect(companyInitials("ABC Technologies Pvt. Ltd.")).toBe("AT");
    expect(companyInitials("Northwind Systems")).toBe("NS");
    expect(companyInitials("The Acme Corporation")).toBe("A");
    expect(companyInitials("Zatpat")).toBe("Z");
    // Never empty, whatever it is handed.
    expect(companyInitials("   ")).toBe("?");
    expect(companyInitials("—")).toBe("?");
  });

  it("initials skip a purely numeric word when a letter word survives", () => {
    /* A registration number or a year is not an initial anyone recognises:
     * "Acme 1789026564183" gave "A1", which identifies nothing in a list. */
    expect(companyInitials("Acme 1789026564183")).toBe("A");
    expect(companyInitials("Acme Systems 2019")).toBe("AS");
    // ...but a name that is genuinely all digits still produces something.
    expect(companyInitials("1789026564183")).toBe("1");
  });

  it("the client count says what it counts", () => {
    expect(clientCountLabel(1)).toBe("1 client");
    expect(clientCountLabel(18)).toBe("18 clients");
    expect(clientCountLabel(0)).toBe("0 clients");
  });

  it("the avatar is hidden from assistive tech — the name is beside it", () => {
    const html = renderToStaticMarkup(<ClientAvatar name="Northwind Systems" />);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain("NS");
  });

  it("duplicate detection folds case and punctuation, not the legal suffix", () => {
    expect(nameKey("ABC Technologies")).toBe(nameKey("abc  technologies"));
    expect(nameKey("Acme Ltd.")).toBe(nameKey("ACME LTD"));
    // "Acme" and "Acme Pvt Ltd" stay DIFFERENT: they are plausibly two
    // companies, and this only decides whether to ask.
    expect(nameKey("Acme")).not.toBe(nameKey("Acme Pvt Ltd"));
  });

  it("activity is described in words a non-legal reader knows", () => {
    expect(activityWords("counterparty.created")).toBe("Client profile created");
    expect(activityWords("analysis.run_recorded")).toBe("Document analyzed");
    expect(activityWords("contract.counterparty_linked"))
      .toBe("Document linked to this client");
    // An action nobody named still appears, rather than being dropped: the
    // trail is append-only and a row that happened must not vanish.
    expect(activityWords("something.new")).toBe("something.new");
  });

  it("a saved profile REPLACES the old one rather than layering over it", () => {
    /* The API omits a cleared field rather than nulling it, so `{...old,
     * ...saved}` would quietly keep a city somebody just deleted. */
    const before = client({ city: "Mumbai", contracts: [doc()], documents: 1 });
    // The server's response to "clear the city": the key is simply gone.
    const saved = client();
    const merged = mergeProfile(before, saved);
    expect(merged.city).toBeUndefined();
    // ...while the parts a PATCH never returns are carried over.
    expect(merged.contracts).toHaveLength(1);
    expect(merged.documents).toBe(1);
  });
});
