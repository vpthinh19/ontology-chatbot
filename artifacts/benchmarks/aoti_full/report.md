# AOTInductor: toàn bộ vòng sinh T5Gemma2

Trạng thái: **ok**.

**Truy vấn AOTI giống `model.generate` thường: 40/40.**

| cấu hình | đúng target | giống model.generate | median/câu |
|---|---:|---:|---:|
| model.generate thường | 32/40 | 40/40 | 2,314.5 ms |
| AOTI toàn vòng | 32/40 | 40/40 | 696.3 ms |
| CT2 GPU float32 | — | — | 1.222 ms (mốc) |

| dựng gói | cỡ hai gói | VRAM đỉnh khi dựng | VRAM đỉnh AOTI |
|---:|---:|---:|---:|
| 76.1 s | 1,042 MiB | 1,870 MiB | 537 MiB |

Mốc so sánh do đề bài cung cấp: model thường 2.569 ms/câu; CT2 GPU float32 1.222 ms/câu.

## Cấu trúc đường chạy

`encoder.pt2` chạy encoder và tính cross-K/V của cả 18 lớp đúng một lần. `decoder.pt2` chạy một token, dùng self-K/V cấp sẵn đến 320 vị trí và cập nhật tensor tại chỗ. Vòng dừng EOS nằm trong lớp Python mỏng; đường chạy không nạp model Transformers và không gọi `model.generate`.

## ldd của `.so`

`encoder.pt2:encoder/data/aotinductor/model/chs2e3ukya4lbobmlchzlxoxcjwc5s5iqckqh4qiv5xodtv4pmre.wrapper.so`

```text
linux-vdso.so.1 (0x00007f1456843000)
	libtorch.so => not found
	libtorch_cpu.so => not found
	libgomp.so.1 => /lib64/libgomp.so.1 (0x00007f1435c83000)
	libcuda.so.1 => /lib64/libcuda.so.1 (0x00007f142f000000)
	libtorch_cuda.so => not found
	libstdc++.so.6 => /lib64/libstdc++.so.6 (0x00007f142ec00000)
	libm.so.6 => /lib64/libm.so.6 (0x00007f142eee9000)
	libgcc_s.so.1 => /lib64/libgcc_s.so.1 (0x00007f1435c54000)
	libc.so.6 => /lib64/libc.so.6 (0x00007f142ea07000)
	libpthread.so.0 => /lib64/libpthread.so.0 (0x00007f1435c50000)
	libdl.so.2 => /lib64/libdl.so.2 (0x00007f1435c4c000)
	librt.so.1 => /lib64/librt.so.1 (0x00007f1435c46000)
	/lib64/ld-linux-x86-64.so.2 (0x00007f1456845000)
ldd: warning: you do not have execution permission for `/tmp/aoti-full-ldd-g3wvazvz/encoder-0.so'
```

`decoder.pt2:decoder/data/aotinductor/model/cvqf3pwyzdf6g7c76zmzf45t3rtlzm2kv52i7kuuewdqq75lfoyy.wrapper.so`

```text
linux-vdso.so.1 (0x00007f619fa0a000)
	libtorch.so => not found
	libtorch_cpu.so => not found
	libgomp.so.1 => /lib64/libgomp.so.1 (0x00007f617f985000)
	libcuda.so.1 => /lib64/libcuda.so.1 (0x00007f6178c00000)
	libtorch_cuda.so => not found
	libstdc++.so.6 => /lib64/libstdc++.so.6 (0x00007f6178800000)
	libm.so.6 => /lib64/libm.so.6 (0x00007f617f86c000)
	libgcc_s.so.1 => /lib64/libgcc_s.so.1 (0x00007f617f83f000)
	libc.so.6 => /lib64/libc.so.6 (0x00007f6178607000)
	libpthread.so.0 => /lib64/libpthread.so.0 (0x00007f617f83b000)
	libdl.so.2 => /lib64/libdl.so.2 (0x00007f617f837000)
	librt.so.1 => /lib64/librt.so.1 (0x00007f617f831000)
	/lib64/ld-linux-x86-64.so.2 (0x00007f619fa0c000)
ldd: warning: you do not have execution permission for `/tmp/aoti-full-ldd-g3wvazvz/decoder-0.so'
```
