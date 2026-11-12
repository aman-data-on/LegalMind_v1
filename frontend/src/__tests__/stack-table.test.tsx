import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { StackTable } from "@/components/StackTable";

describe("StackTable (B3 page 2: a table becomes a stacked list on a phone)", () => {
  it("labels each cell by its column, skips a hidden column, keeps the row's own attributes", () => {
    const html = renderToStaticMarkup(
      <StackTable columns={[{ label: "Point" }, { label: "Status" }, { label: "Actions", hidden: true }]}>
        {[1, 2].map((n) => (
          <tr key={n} data-finding-id={`f${n}`}>
            <td>Name {n}</td>
            {n === 1 ? <td>Missing</td> : <td>Matches</td>}
            <td><button type="button">Open</button></td>
          </tr>
        ))}
      </StackTable>,
    );
    expect(html).toContain('class="ws-docs__table lm-stack"');
    expect(html).toContain('data-finding-id="f2"');
    expect(html.match(/data-label="Point"/g)).toHaveLength(2);
    expect(html.match(/data-label="Status"/g)).toHaveLength(2);
    expect(html).not.toContain('data-label="Actions"');
    expect(html).toContain('<span class="ws-visually-hidden">Actions</span>');
    expect(html.match(/role="cell"/g)).toHaveLength(6);
  });
});
