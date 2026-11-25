"use client";

import dynamic from "next/dynamic";

/** W2-1/W2-2: the root 404 is part of every page's tree, so whatever it imports statically
 *  loads on every page — /login included. Its body (the shell, its sheet, the labels) is a
 *  dynamic import here, so it loads only when a 404 actually renders. A dynamic import in
 *  the server-component not-found.tsx itself would not split (Next lazy-loading guide). */
export const NotFoundBody = dynamic(() => import("./notFoundBody"));
