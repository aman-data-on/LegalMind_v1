/**
 * The ONE data table that becomes a stacked list on a phone (UX Batch 3, DESIGN-FOUNDATION §2.4).
 * Above 640px it is the page's ordinary table. Below, every row is a card: the first cell is its
 * title, each other cell reads "Label  value", an unlabelled cell (row actions) sits at the foot.
 * Nothing scrolls sideways (WCAG 1.4.10).
 *
 * The pages keep writing their own `<tr>`/`<td>`; this stamps each cell with its column's label
 * (`data-label`, read by CSS) and sets explicit roles, because `display: block` makes some
 * browsers drop table semantics. Presentation only (rule 18).
 */

import { Children, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";

export interface StackColumn {
  label: string;
  /** shown to screen readers only (an actions column) — the card gets no label for it */
  hidden?: boolean;
  className?: string;
}

type Props = { children?: ReactNode; className?: string; role?: string; "data-label"?: string };

export function StackTable({ columns, children, className = "" }: {
  columns: StackColumn[];
  /** the `<tr>` rows, cells in column order */
  children: ReactNode;
  className?: string;
}) {
  const rows = Children.map(children, (row) => {
    if (!isValidElement<Props>(row)) return row;
    let i = 0;
    const cells = Children.map(row.props.children, (cell) => {
      if (!isValidElement<Props>(cell)) return cell;
      const column = columns[i++];
      return cloneElement(cell as ReactElement<Props>, {
        role: "cell", ...(column && !column.hidden ? { "data-label": column.label } : {}),
      });
    });
    return cloneElement(row, { role: "row" }, cells);
  });
  return (
    <div className={`ws-docs__table lm-stack ${className}`.trim()}>
      <table role="table">
        <thead>
          <tr role="row">
            {columns.map((column) => (
              <th key={column.label} scope="col" role="columnheader" className={column.className}>
                {column.hidden ? <span className="ws-visually-hidden">{column.label}</span> : column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}
