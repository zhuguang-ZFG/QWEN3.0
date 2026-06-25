"""Few-shot example bank for pen-plotter drawing prompts.

Separated from draw_prompt_enhancer.py to keep the enhancer under the 300-line
file-size guard. Pure data, no logic.
"""

from __future__ import annotations

# ponytail: few-shot bank as a plain string constant. Ceiling: grows linearly
# with example count; at ~50 examples consider a list joined at load time.
# Upgrade path: move to a JSON/MD resource file when examples need per-locale
# or per-model variants.

PLOTTER_FEW_SHOT = (
    "【正面示例】"
    "用户：画一只猫 → 生成：一只猫的简笔画，侧面轮廓，黑线白底，封闭轮廓，约15笔画。"
    "用户：画个苹果 → 生成：一个苹果的轮廓线，带小蒂，黑线白底，封闭图形。"
    "用户：画一棵树 → 生成：一棵树的简笔画，树冠用三个圆形堆叠轮廓，树干矩形，黑线白底，封闭轮廓。"
    "用户：画一朵花 → 生成：一朵花的简笔画，五瓣花冠围绕中心圆，茎直线，黑线白底，封闭轮廓。"
    "用户：画一栋房子 → 生成：房子简笔画，三角屋顶+矩形墙体+方形窗户+长方形门，黑线白底，封闭轮廓。"
    "用户：画一颗心 → 生成：心形简笔画，对称双弧闭合，黑线白底，单笔封闭轮廓。"
    "用户：画一颗五角星 → 生成：五角星简笔画，五条直线交叉闭合，黑线白底，单笔可完成。"
    "用户：画一条鱼 → 生成：鱼简笔画，椭圆身体+三角尾+小圆眼，黑线白底，封闭轮廓。"
    "用户：写「你好」 → 生成：直接输出「你好」两字，黑线白底，按笔画顺序书写。"
    "【负面示例】"
    "用户：画一只毛茸茸的猫在阳光下的照片 → 拒绝：过于复杂，包含毛发、光影、背景。"
    "用户：画一座城市和人群 → 拒绝：主体过多，超出单笔画能力。"
    "用户：画一只带彩色项圈在草地上奔跑的狗 → 拒绝：含颜色、背景、动态姿势，超能力。"
    "用户：画一个戴着帽子拿着气球的小女孩 → 拒绝：多道具+人物细节过多，建议简化为「画一个小女孩」。"
    "用户：画一幅山水画有远山近水和小船 → 拒绝：风景多主体+层次，建议简化为「画一座山」或「画一条船」。"
    "用户：画一个动漫美少女 → 拒绝：人物面部细节/头发线条过密，超单笔能力。"
    "用户：画一只猫并写上它的名字 → 拒绝：禁止文字+图像混合，请分开请求「画一只猫」或「写名字」。"
)
