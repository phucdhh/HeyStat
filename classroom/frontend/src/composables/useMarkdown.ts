import MarkdownIt from 'markdown-it';
// @ts-ignore
import mk from 'markdown-it-katex';
import 'katex/dist/katex.min.css';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

md.use(mk);

export function useMarkdown() {
  const renderMarkdown = (text: string | null | undefined): string => {
    if (!text) return '';
    return md.render(text);
  };

  return { renderMarkdown };
}
