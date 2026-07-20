import React from 'react';
import { Box, Text } from '../../ink.js';

/**
 * Openlab Robot 内核提示：
 * 提示用户当前为 cc-haha 内核；使用 jiuwen-Agent-core 内核时请改用 `jiuwen` 命令启动。
 */
export function KernelHint() {
  return (
    <Box paddingLeft={2} flexDirection="column">
      <Text dimColor={true}>
        Kernel: cc-haha · To use the jiuwen-Agent-core kernel, start with the `jiuwen` command instead.（使用 jiuwen-Agent-core 内核请改用 jiuwen 命令启动）
      </Text>
    </Box>
  );
}
