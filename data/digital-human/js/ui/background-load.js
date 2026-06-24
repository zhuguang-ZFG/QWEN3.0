// 背景加载检测：等待当前激活图层的视频/图片加载完成后显示模型加载提示
(function () {
    const modelLoading = document.getElementById('modelLoading');
    if (!modelLoading) return;

    function showLoading() {
        modelLoading.style.display = 'flex';
    }

    function bindToActiveLayer() {
        const activeLayer = document.querySelector('.bg-layer.bg-layer--active');
        const media = activeLayer ? activeLayer.querySelector('video, img') : null;

        if (!media) {
            // 没有动态背景时直接显示
            showLoading();
            return;
        }

        if (media.tagName === 'VIDEO') {
            if (media.readyState >= 3) {
                showLoading();
            } else {
                media.addEventListener('loadeddata', showLoading, { once: true });
                media.addEventListener('error', showLoading, { once: true });
            }
        } else {
            if (media.complete) {
                showLoading();
            } else {
                media.addEventListener('load', showLoading, { once: true });
                media.addEventListener('error', showLoading, { once: true });
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindToActiveLayer);
    } else {
        bindToActiveLayer();
    }
})();
