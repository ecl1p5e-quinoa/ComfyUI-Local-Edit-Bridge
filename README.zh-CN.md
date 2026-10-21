# Local Edit Bridge for ComfyUI

[English](README.md) | 简体中文

在原图上涂出想改的地方，把裁剪图交给图像编辑模型，拿到结果后再放回 ComfyUI。这个插件负责裁剪、生成位置参考图，以及把修改后的区域拼回原图。

项目目前还处于接近 MVP 的早期阶段。基本流程已经能用，但还有需要打磨的地方。现在主要面向一个人在本机上，一次完成一处局部修改。

插件不会调用图像 API、自动上传图片、操作聊天网页或下载模型。发送文件和保存模型返回的图片，都由你手动完成。插件本身不需要 API key；使用外部图像服务所需的账号或权限，需要你自行准备。

## 现在能做什么

- 画蒙版、擦除、撤销笔画，也可以缩放和平移画布。
- 预览实际发给模型的裁剪图，调整周围保留多少内容。
- 把两张图和可以自行修改的提示词放进同一个文件夹。
- 返回前面的步骤修改，不丢掉已经画好的蒙版和写好的提示词。
- 调整颜色匹配、扩大拼接范围、柔化边缘。
- 滑动查看修改前后，或按住查看原图、松开查看结果。
- 重新打开已保存的任务，也可以把结果接进普通 ComfyUI 工作流。

![编辑器预览](docs/editor-roundtrip.png)

## 安装

先准备一个能正常运行的 ComfyUI，Python 版本需要在 3.10 或以上。插件用到 Pillow、NumPy 和 SciPy。安装这些依赖时，要用运行 ComfyUI 的那个 Python，否则可能装完了，ComfyUI 还是找不到。

如果你之前已经安装了旧名称的文件夹 `comfyui-gpt-local-edit-helper`，直接更新那一份即可，不要再并排安装一份。

### Windows 便携版

在便携版的根目录打开 PowerShell，也就是同时放着 `ComfyUI` 和 `python_embeded` 两个文件夹的位置。依次运行：

```powershell
git clone https://github.com/ecl1p5e-quinoa/ComfyUI-Local-Edit-Bridge.git .\ComfyUI\custom_nodes\ComfyUI-Local-Edit-Bridge
.\python_embeded\python.exe -m pip install -r .\ComfyUI\custom_nodes\ComfyUI-Local-Edit-Bridge\requirements.txt
```

安装后重启 ComfyUI。只刷新网页不会让它加载新插件。

### 使用普通 Python 环境的 ComfyUI

在 `ComfyUI` 文件夹中打开终端，先激活你平时启动 ComfyUI 时使用的 Python 环境，再运行：

```sh
git clone https://github.com/ecl1p5e-quinoa/ComfyUI-Local-Edit-Bridge.git custom_nodes/ComfyUI-Local-Edit-Bridge
python -m pip install -r custom_nodes/ComfyUI-Local-Edit-Bridge/requirements.txt
```

运行完后重启 ComfyUI。

如果没有安装 Git，可以在本仓库的 GitHub 页面点击 **Code → Download ZIP**。解压后，把插件放到 `ComfyUI/custom_nodes/ComfyUI-Local-Edit-Bridge`。打开这个文件夹应该直接看到 `__init__.py`、`requirements.txt` 和 `web`，不要在里面再套一层仓库文件夹。然后按上面对应版本的命令安装依赖。

### 从哪里打开

启动 ComfyUI 后，下面三种方式任选一种：

- 在菜单中选择 **Tools → Open Local Edit Bridge**。
- 搜索并添加 **Local Edit Bridge** 节点，点击节点上的 **Open Editor**。节点分类是 `image/local edit`。
- 直接打开[编辑器页面](http://127.0.0.1:8188/gpt-local-edit/editor)。如果你的 ComfyUI 不是用 `8188` 端口，替换成实际端口即可。

只使用编辑器时，不需要搭建或运行节点工作流。想把结果继续接到 ComfyUI 里处理时，才需要用到这个节点。

以后更新时，在已安装的插件文件夹中运行 `git pull`，然后重启 ComfyUI 并刷新编辑器。

## 第一次使用

宽屏下，前两个步骤会左右并排显示。按步骤编号操作，最后到页面底部的大图检查修改前后。下面保留了界面上的英文按钮名，方便你找到对应位置。

### 第 1 步：导入原图，涂出要修改的地方

点击 **Load image**，或者把本地图片拖进 **Original & edit**。如果想保留图片中记录的生成信息，可以优先使用 PNG。

用 **Brush** 涂抹要修改的区域，用 **Eraser** 擦掉多余的部分。画布上的半透明色块就是选中的区域。保存成黑白蒙版后，白色表示修改，黑色表示保留。

- **Brush size** 调整笔刷大小，光标下的圆圈会显示实际大小。
- **Undo** 和 **Redo** 用于撤销和重做笔画。也可以用 Ctrl/Cmd+Z 撤销，Ctrl/Cmd+Shift+Z 或 Ctrl+Y 重做。这些快捷键在鼠标位于画布上或画布获得焦点时生效；文本框仍使用正常的文字编辑快捷键。
- 滚轮缩放；按住空格拖动，或按住鼠标中键拖动，可以移动画面。点击 **Fit view** 让整张图重新适应画布大小。

**Image metadata** 中可以查看插件读到的生成信息，包括常见的 ComfyUI 和 A1111/Forge PNG 信息。自定义工作流不一定都能识别，所以也保留了原始 PNG 文本供查看。

### 第 2 步：确认发给模型的裁剪图

**Exact GPT crop** 显示不带蒙版的裁剪图。之后导出的两张图都使用这个范围，不是整张原图。

| 设置 | 用来做什么 |
| --- | --- |
| Crop factor | 调整蒙版周围多保留多少画面，默认是 2。 |
| Minimum px | 设置裁剪图的最小尺寸，前提是原图还有足够空间。 |
| Multiple of | 尽量让宽和高成为所选数字的整数倍。没有特殊需求时保持 1 即可。 |
| Square crop | 尽量裁成正方形。 |
| Output size | 保留裁剪区域原本的像素尺寸，或把最长边缩小到不超过 1024 像素。 |

裁剪不会超出原图，也会优先保证覆盖你画的蒙版。靠近图片边缘时，可能无法同时满足正方形或尺寸倍数的要求。

### 第 3 步：准备文件，发给模型

1. 在 **Your edit request** 中写下想修改什么。
2. 如果需要，展开 **Optional selected generation context**，补充角色特征或原图的生成信息。插件不会自动把图片中的所有信息塞进提示词。
3. 点击 **Build editing prompt**，检查 **Final prompt** 中的文字，有不合适的地方可以直接改。
4. 点击 **Prepare for GPT & open folder**。插件会保存这次准备好的内容，并打开一个只包含以下三个文件的文件夹：

| 文件 | 用途 |
| --- | --- |
| `01-crop.png` | 不带蒙版的裁剪图，让模型在这张图上修改。 |
| `02-overlay.png` | 同一张裁剪图，带半透明色块，告诉模型要改哪里。 |
| `prompt.txt` | 你确认过的修改要求。 |

全选这三个文件，拖进图像编辑模型的会话。如果使用的服务不接受文本文件，就上传两张图，再把 `prompt.txt` 的内容粘贴到消息里。让模型返回修改后的干净裁剪图，不要把位置参考图上的色块画进结果。

**More options** 里放着复制提示词、下载两张图、重新打开文件夹，以及 **Mark as sent**。后者只是把任务标记为已发送，不点也可以直接导入结果。

准备完成后，前面的编辑控件会暂时锁定。需要修改时，点击对应步骤的 **Rework this step**。刷新页面前先完成准备，让提示词保存下来；还没保存的文字修改可能会丢失。

### 第 4 步：把模型返回的图片导入回来

先把模型生成的图片保存到本机，再把这个文件拖进 **Returned edit**，或点击 **Import GPT result** 选择文件。直接从聊天网页拖图片，有时传过来的只是链接，编辑器无法导入。

**Import fitting** 默认是 **Fit inside crop**，会保持返回图片的比例，把它放进裁剪范围，剩余空间用透明区域补齐。**Check aspect ratio (strict)** 只接受宽高比相对偏差不超过 2% 的图片。如果它拒绝导入，切换到 **Fit inside crop**，再点 **Retry selected image**。

插件会调整图片尺寸，但不会自动移动或旋转图中的内容，让它与原图对齐。

### 第 5 步：调整拼接效果，检查并保存

可以先保留默认设置，点击 **Composite & preview seam** 看看效果。

| 设置 | 用来做什么 |
| --- | --- |
| Color match | 参考周围画面的颜色，尝试让返回图与原图更接近。默认开启。 |
| Strength | 控制颜色修正的强度。默认是 1，表示完整应用这次修正。 |
| Mask expansion px | 扩大最终拼接的范围，按原图像素计算，可设 0–128，默认是 0。 |
| Inward feather px | 从拼接边缘向内做柔和过渡。 |
| Seam width px | 设置供后续修边使用的蒙版，在边界内外各延伸多少像素。 |

遮罩扩展只影响最终拼接范围，不会改掉你画的蒙版，也不会改变已经发给模型的图片。扩展到裁剪图边缘就会停止；如果空间不够，需要在第 2 步扩大裁剪范围，再重新准备一次编辑。每次预览都从原始蒙版重新计算，不会越点越大。

到页面底部的 **Before / after** 检查效果。**Slide** 可以移动分界线查看前后差别；**Hold for Before** 则是按住显示原图，松开显示结果。

满意后，点击 **Finalize PNG**，把 `final.png` 保存到任务文件夹。再点 **Save final PNG**，可以通过浏览器下载一份。保存结果会保留原图尺寸和透明度，最终拼接蒙版以外的像素保持不变。

## 想回到前面重做怎么办

点击步骤标题旁的 **Rework this step**。它会让这个步骤重新可编辑，并清除后面依赖它的结果，但保留你已经填好的内容。重新画蒙版不会清空提示词，重新写提示词也不会清空蒙版。

**Undo rework** 可以回到最近一次返工之前，**Redo rework** 可以再切回来。编辑器只保留一份这样的临时记录：只要 ComfyUI 没有重启，刷新网页后仍然可以使用；再次返工会替换它，重启 ComfyUI 会清除它。

画笔的撤销记录是另一回事。它有内存上限，而且只在这张图保持打开时有效。

## 文件保存在哪里

在 **Active job** 中选择已保存的任务，就可以继续处理。每次导入新的原图，都会创建一个新任务。

默认保存位置是：

```text
ComfyUI/output/gpt_local_edit/jobs/<job-id>/
```

如果你改过 ComfyUI 的输出目录，任务也会保存在对应位置。第 3 步的 **Local job folder** 可以展开查看并复制准确路径。

任务文件夹里会保存原图、蒙版、裁剪图、提示词、返回图、当前拼接图和最终结果。`metadata.json` 记录设置；`gpt-handoff` 子文件夹只放发给模型的三个文件。

每一部分只保留当前最新的文件，不会把每次尝试都存成一份历史。返工撤销用的是任务文件夹外的一份临时副本。重新打开旧任务时，插件也会清理自己已经替换掉的旧文件，不会动其他文件或其他任务。尽量不要在两个标签页里同时修改同一个任务：其中一页保存后，另一页需要重新加载最新内容。

原图中的 PNG 文本和颜色配置文件会保留，最终 PNG 还会加上这次编辑的记录。原来的生成提示词仍然只是原图的生成记录，不一定能准确描述修改后的图片。

## 和普通局部重绘有什么不同

如果你用过 SDXL 或 Anima 的局部重绘，这套流程应该很熟悉：选中一块区域，带上周边画面裁出来，生成修改结果，再拼回去。可以理解成把原本由 K 采样器负责的生成环节，换成外部图像编辑模型。这是在类比它们在流程中做什么，并不是说内部原理或参数相同。

界面以 GPT 为例，但只要其他服务能够接收图片和文字，并返回修改后的图片，也可以用这套流程。不过，按我的使用体验，其他模型的效果可能会比 gpt-image-2 差很多。

下面是我的个人使用经验。在大多数图片编辑和理解提示词的任务上，我觉得 GPT 比 SDXL / Anima 强很多。但如果你保留了生成原图时用的模型和设置，传统局部重绘往往更容易保持原图风格和角色特征。

### 重绘区域可能有噪点

GPT-image 有时会生成噪点。虽然提示词中已经要求避免噪点，仍然不能完全杜绝。我的处理方法是，对有噪点的区域再做一次传统 SDXL 局部重绘，把去噪强度设得非常低。

### 缩放后可能出现锯齿

这套流程涉及图片缩放，边缘可能出现锯齿。按我的经验，不做其他修改，只把图片过一次 VAE 编码和解码，可以缓解这个问题。

### 复杂角色的特征可能被改掉

修复人物结构时，如果角色特征比较复杂，比如 anthro furry 类角色，或原图用了角色 LoRA，GPT 可能在修好结构的同时改掉角色原本的特征。可以试着在提示词里更明确地描述这些特征，但我的体验是，帮助往往有限。

### 半透明蒙版只是位置参考

参考图上的色块是帮助模型理解哪里要改，不等于给图像编辑 API 传入严格的蒙版。模型完全可能连色块以外的内容也一起改了。如果这些额外修改让拼接边缘显得生硬，可以尝试增大第 5 步的 **Mask expansion px**，把附近更多修改包含进来。

## 可选：回到 ComfyUI 里继续修边

完成拼接后，在编辑器中点击 **Copy ID**，把任务编号粘贴到 **Local Edit Bridge** 节点的 `job_id` 中。节点会输出拼接图、接缝附近的一圈蒙版、提示词和任务信息。

可以把[示例工作流](examples/seam_refinement.json)加载到 ComfyUI，再选择你自己的兼容模型。它使用 VAEEncode、SetLatentNoiseMask、KSampler、VAEDecode 和 ImageCompositeMasked 节点，不会替你下载模型。

可以从 **0.08–0.25** 的去噪强度开始，按图片效果调整。保留最后的 **ImageCompositeMasked** 节点：VAE 编码和解码可能改变采样区域以外的像素，这个节点会把不需要修改的周围画面放回去。如果 VAE 无法直接处理原图尺寸，先补边，解码后再裁回原尺寸，最后拼接。

这一步在 ComfyUI 工作流中完成。编辑器里暂时没有一键采样按钮。

## 常见问题和目前的限制

| 遇到的问题 | 可以怎么处理 |
| --- | --- |
| 找不到节点或菜单入口 | 检查插件文件夹是否放对，重启 ComfyUI，再刷新网页。也可以查看 ComfyUI 终端里是否提示缺少依赖。 |
| 更新后点击按钮报 405 | 重启 ComfyUI，让它加载更新后的插件，再刷新编辑器。 |
| 拖入返回图没有反应 | 先把图片保存成本地文件，查看第 4 步的提示，然后重试，或直接用文件选择按钮。 |
| 准备好了，但文件夹没打开 | 在运行 ComfyUI 的那台电脑上，通过本机地址使用编辑器。也可以复制 **Local job folder** 中的路径，或从 **More options** 下载两张图并复制提示词。 |
| 蒙版或提示词不能修改 | 点击对应步骤的 **Rework this step**。 |
| 颜色匹配似乎没效果 | 周围需要留有足够多未修改的画面，返回图的对应区域也不能透明。可用像素太少时，会跳过修正。 |
| 旧任务要求导入整图，而不是裁剪图 | 返工第 3 步，重新生成提示词并完成准备，就会切换到当前的两张裁剪图格式。 |

上传文件不能超过 32 MiB，图片不能超过 2400 万像素，目前只支持 8 位图片。这个工具面向本机单人使用，没有账号权限管理。

目前还没有自动位置对齐、同一任务的多个候选结果管理、跨会话保存笔画历史、跨电脑迁移任务，以及从系统剪贴板粘贴图片。更好的对齐、候选图对比和更方便的修边，是后续可以完善的方向，还不是现成功能。

<details>
<summary>想了解拼接的具体处理方式</summary>

颜色匹配会读取蒙版外侧的一圈画面，比较各颜色通道的平均值和变化幅度，并跳过返回图中的透明像素。至少需要 64 个可用像素。缩放修正限制在 0.8–1.25，平均值偏移不超过 32/255；如果某个通道几乎是纯色，就只调整平均值。每次预览都从导入的图片重新处理，不会一层层叠加修正。

颜色计算直接使用图片里存储的 RGB 数值。保留颜色配置文件，并不代表插件会先转换到线性光空间再拼接。

边缘柔化只在蒙版内部进行，也会考虑返回图片的透明度。供后续修边的蒙版，是把扩大后的蒙版减去缩小后的蒙版，留下边界两侧的一圈区域。

裁剪坐标使用整数像素。右边和下边的坐标表示裁剪停止的位置，不包含该坐标处的像素。

</details>

## 开发

图片处理的 Python 代码与 ComfyUI、Torch 分开。`prompt` 负责组装提示词，`bridge/manual.py` 负责各个编辑步骤，`comfy` 负责连接 ComfyUI，`web` 是浏览器编辑器。

如果想在本地修改代码，在插件文件夹中打开终端，用普通 Python 安装创建开发环境：

```sh
python -m venv .venv
```

PowerShell 中运行 `.venv\Scripts\Activate.ps1` 激活环境；Linux/macOS 中使用 `source .venv/bin/activate`，然后运行：

```sh
python -m pip install -e ".[dev]"
python -m pytest --confcutdir=tests tests
```

这个环境只用于开发。平时使用插件不需要激活它，也不用在里面另外安装 Torch。

<details>
<summary>如果便携版 Python 没有 venv</summary>

开发时使用的便携版 Python 3.13.9 需要改用 `virtualenv`。在 `ComfyUI/custom_nodes` 下的插件文件夹中打开 PowerShell，运行：

```powershell
..\..\..\python_embeded\python.exe -m pip install --target .devtools virtualenv
..\..\..\python_embeded\python.exe -c "import sys; sys.path.insert(0, '.devtools'); import virtualenv; virtualenv.cli_run(['.venv'])"
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests tests
```

</details>

`tools/make_fixture.py` 用来生成测试图片。`tools/browser_smoke.cjs` 通过 Playwright 和已安装的 Edge 检查编辑器，不会打开 ChatGPT。运行前把 `NODE_PATH` 设为包含 Playwright 包的目录，并传入本地服务器地址和开发环境的 Python 路径。以往的测试结果见[验证记录](docs/VALIDATION.md)。

## 参考项目与许可证

裁剪、拼接和颜色匹配都是已有的方法。这个项目把它们放进一个编辑器，方便你把图片交给外部模型修改，再拿回本地使用。

参考项目包括 [InpaintCanvas](https://github.com/DenRakEiw/ComfyUI-InpaintCanvas)、[CropStitch-NB2](https://github.com/amortegui84/comfyui-inpaint-cropstitch-nb2)、[NKD Basic Tools](https://github.com/Nekodificador/ComfyUI-NKD-Basic-Tools) 和 [CropAndStitch](https://github.com/lquesada/ComfyUI-Inpaint-CropAndStitch)。前后对比的交互参考了 [rgthree Image Comparer](https://github.com/rgthree/rgthree-comfy)。

本项目没有复制或打包这些项目的代码。这里的原创代码采用 [MIT 许可证](LICENSE)，参考项目保留各自的许可证。更多记录见[源码查阅记录](docs/PRIOR_ART.md)、[设计说明](docs/MVP_DESIGN.md)和[第三方说明](THIRD_PARTY.md)。
