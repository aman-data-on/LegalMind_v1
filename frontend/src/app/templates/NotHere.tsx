/** For a reader without `legal.approve_customization` the section does not exist
 *  (absent, not disabled): the same words as any unknown address. */
export function NotHere() {
  return (
    <div className="ws-docs tpl">
      <h1>Page not found</h1>
      <p>This address doesn&rsquo;t exist, or the page has moved.</p>
    </div>
  );
}
