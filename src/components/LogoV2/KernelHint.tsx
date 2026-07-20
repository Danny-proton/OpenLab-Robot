import React from 'react';
import { Box, Text } from '../../ink.js';
import { getBrandAppName } from '../../utils/brandConfig.js';

/**
 * Openlab Robot 内核提示：
 * 提示用户当前为 Claude Code 安全修复版内核；
 * 使用 jiuwen-Agent-core 内核时请改用 `jiuwen` 命令启动。
 */
export function KernelHint() {
  return (
    <Box paddingLeft={2} flexDirection="column">
      <Text dimColor={true}>
        {`${getBrandAppName()} · Kernel: Claude Code 安全修复版 · To use the jiuwen-Agent-core kernel, start with the \`jiuwen\` command instead.（使用 jiuwen-Agent-core 内核请改用 jiuwen 命令启动）`}
      </Text>
    </Box>
  );
}
