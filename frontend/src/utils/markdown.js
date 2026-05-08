import MarkdownIt from "markdown-it";

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
});

const defaultLinkOpen =
  markdown.renderer.rules.link_open ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));
const defaultLinkClose =
  markdown.renderer.rules.link_close ||
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));
const imagePreviewStack = [];

markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const href = tokens[idx].attrGet("href") || "";
  const nextToken = tokens[idx + 1];
  const text = nextToken?.type === "text" ? nextToken.content : "";
  const shouldPreview = isImageUrl(href) || /图片|查看|点击查看/i.test(text);

  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noopener noreferrer");
  imagePreviewStack.push(shouldPreview ? href : "");

  return defaultLinkOpen(tokens, idx, options, env, self);
};

markdown.renderer.rules.link_close = (tokens, idx, options, env, self) => {
  const href = imagePreviewStack.pop();
  const closeTag = defaultLinkClose(tokens, idx, options, env, self);
  if (!href) return closeTag;

  return `${closeTag}<a class="markdown-image-link" href="${escapeAttribute(href)}" target="_blank" rel="noopener noreferrer"><img class="markdown-image-preview" src="${escapeAttribute(href)}" alt="图片预览" loading="lazy" /></a>`;
};

export function renderMarkdown(content) {
  return markdown.render(normalizeMarkdown(content));
}

function normalizeMarkdown(content) {
  return (content || "")
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function isImageUrl(url) {
  return /\.(png|jpe?g|gif|webp|bmp|svg)(\?.*)?$/i.test(url);
}

function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
