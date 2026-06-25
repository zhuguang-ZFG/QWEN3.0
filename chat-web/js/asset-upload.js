/* Asset upload helper for the chat console. */

(function () {
  "use strict";

  const API = "/device/v1/app/assets";
  const MAX_SIZE = 2 * 1024 * 1024;

  function getToken() {
    return window.LiMaAuth ? LiMaAuth.getToken() : "";
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("读取文件失败"));
      if (file.type === "image/svg+xml" || file.name.toLowerCase().endsWith(".svg")) {
        reader.readAsText(file);
      } else {
        reader.readAsDataURL(file);
      }
    });
  }

  function categoryForFile(file) {
    const name = file.name.toLowerCase();
    if (name.endsWith(".svg")) return "svg";
    return "image";
  }

  async function handleAssetUpload(input) {
    const token = getToken();
    if (!token) {
      showToast("请先登录后再上传素材", { error: true });
      input.value = "";
      return;
    }
    const file = input.files && input.files[0];
    if (!file) return;
    if (file.size > MAX_SIZE) {
      showToast("文件大小超过 2MB 限制", { error: true });
      input.value = "";
      return;
    }

    try {
      const content = await readFile(file);
      const category = categoryForFile(file);
      const title = file.name.replace(/\.[^/.]+$/, "");
      await fetch(API, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + token,
        },
        body: JSON.stringify({
          title,
          category,
          content,
          difficulty: "easy",
          tags: [category],
        }),
      });
      showToast(`素材 "${title}" 已上传到资产库`);
    } catch (err) {
      showToast("上传失败：" + (err.message || "未知错误"), { error: true });
    } finally {
      input.value = "";
    }
  }

  window.handleAssetUpload = handleAssetUpload;
})();
