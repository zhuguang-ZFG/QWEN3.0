// Cloudflare Pages edge worker: redirect apex domain -> www
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.hostname === "donglicao.com") {
      url.hostname = "www.donglicao.com";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
