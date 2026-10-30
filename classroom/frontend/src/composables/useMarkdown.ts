import MarkdownIt from 'markdown-it';
import katex from '@vscode/markdown-it-katex';
import 'katex/dist/katex.min.css';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

// markdown-it-katex (the old package) renders with KaTeX 0.6 markup while this
// app styles with KaTeX 0.16 CSS, so accents, sub/superscripts and fraction
// levels pile up on the same baseline. This plugin uses the installed KaTeX.
md.use(katex, { throwOnError: false, errorColor: '#B91C1C', strict: false });

/** The API stores lesson text HTML-escaped, so `$p < .05$` reaches the parser as
 *  `$p &lt; .05$` and KaTeX fails on the entity. Decoding only the formula body
 *  keeps the rest of the markdown safe from `<` being read as a tag. */
const decodeEntities = (latex: string) => latex
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#0?39;/g, "'")
  .replace(/&amp;/g, '&');

for (const rule of ['math_inline', 'math_block', 'math_inline_block', 'math_inline_bare_block']) {
  const original = md.renderer.rules[rule];
  if (!original) continue;
  md.renderer.rules[rule] = (tokens, idx, options, env, self) => {
    tokens[idx].content = decodeEntities(tokens[idx].content);
    return original(tokens, idx, options, env, self);
  };
}

export function useMarkdown() {
  const renderMarkdown = (text: string | null | undefined): string => {
    if (!text) return '';
    return md.render(text);
  };

  return { renderMarkdown };
}
