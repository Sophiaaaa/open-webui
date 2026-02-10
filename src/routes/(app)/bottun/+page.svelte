<script lang="ts">
    import { onMount, tick } from 'svelte';
    import { getUIConfig, analyzeQuery, generateAndExecuteSQL, getDownloadUrl } from '$lib/apis/bottun';
    import ChatBubble from '$lib/components/bottun/ChatBubble.svelte';
    
    let token = '';
    let uiConfig: any = {};
    let messages: any[] = [];
    let userInput = '';
    let isLoading = false;
    let chatContainer: HTMLElement;
    
    // State
    let currentContext: any = {};
    
    onMount(async () => {
        token = localStorage.getItem('token') || '';
        if (token) {
            uiConfig = await getUIConfig(token);
            // Initial greeting
            messages = [{
                content: "你好！我是数据查询助手。请直接提问，或者点击下方快捷入口。",
                isBot: true,
                context: {}
            }];
        }
    });
    
    async function sendMessage(text: string = '', fromUpdate: boolean = false) {
        if (!text && !userInput && !fromUpdate) return;
        
        const content = text || userInput;
        if (!fromUpdate) {
            messages = [...messages, { content, isBot: false }];
            userInput = '';
        }
        
        isLoading = true;
        await tick();
        scrollToBottom();
        
        try {
            // 1. Analyze
            const analysis = await analyzeQuery(token, content, currentContext);
            
            if (analysis) {
                // Update Context
                currentContext = {
                    kpi: analysis.kpi,
                    time_range: analysis.time_range,
                    scope: analysis.scope,
                    missing_params: analysis.missing_params
                };
                
                // If missing params, Bot asks for them
                if (analysis.missing_params && analysis.missing_params.length > 0) {
                     let replyContent = "我需要更多信息才能查询。";
                     if (analysis.missing_params.includes('kpi')) replyContent = "请选择想要查询的指标 (KPI):";
                     else if (analysis.missing_params.includes('time_range')) replyContent = "请指定时间范围:";
                     else if (analysis.missing_params.includes('scope')) replyContent = `请补充筛选条件 (KPI: ${analysis.kpi}):`;
                     
                     messages = [...messages, {
                         content: replyContent,
                         isBot: true,
                         missingParams: analysis.missing_params,
                         missingScopeCategories: analysis.missing_scope_categories,
                         context: currentContext
                     }];
                } 
                // If finished selection, Execute SQL
                else if (analysis.finished_selection) {
                    messages = [...messages, { content: "正在生成 SQL 并查询...", isBot: true }];
                    await tick();
                    scrollToBottom();
                    
                    const res = await generateAndExecuteSQL(token, currentContext.kpi, currentContext.time_range, currentContext.scope);
                    
                    // Remove "Generating..." message or update it
                    messages.pop();
                    
                    if (res) {
                         // Build summary content
                         let summary = res.summary || "查询完成。";
                         if (res.sql) summary += `\n\n\`\`\`sql\n${res.sql}\n\`\`\``;
                         
                         // Visualization Logic (Mock for now, just text or check columns)
                         const hasData = res.result && res.result.data && res.result.data.length > 0;
                         
                         // Create download URL
                         const dlUrl = hasData ? getDownloadUrl(currentContext.kpi, currentContext.time_range, currentContext.scope) : null;
                         
                         let mdTable = "";
                         if (hasData) {
                             // Simple MD table for first 5 rows
                             const cols = res.result.columns;
                             mdTable = `\n\n| ${cols.join(' | ')} |\n| ${cols.map(() => '---').join(' | ')} |\n`;
                             res.result.data.slice(0, 5).forEach((row: any) => {
                                 mdTable += `| ${Object.values(row).join(' | ')} |\n`;
                             });
                             if (res.result.data.length > 5) mdTable += `| ... | ... |\n`;
                         } else {
                             summary += "\n\n(暂无数据)";
                         }

                         messages = [...messages, {
                             content: summary + mdTable,
                             isBot: true,
                             sql: res.sql,
                             result: res.result,
                             downloadUrl: dlUrl,
                             context: currentContext
                         }];
                    } else {
                         messages = [...messages, { content: "查询失败，请稍后重试。", isBot: true, error: "Backend error", context: currentContext }];
                    }
                } else {
                    // Just informational or weird state?
                    // Maybe "Is proactive scope?" logic handled in backend to trigger missing params
                    // If no missing params but not finished? Probably just updated context.
                    messages = [...messages, { content: "已更新条件。", isBot: true, context: currentContext }];
                }
            }
        } catch (e: any) {
            console.error(e);
            messages = [...messages, { content: "发生错误: " + (e.detail || e.message), isBot: true, error: e, context: currentContext }];
        } finally {
            isLoading = false;
            await tick();
            scrollToBottom();
        }
    }
    
    function scrollToBottom() {
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    function handleParamUpdate(event: CustomEvent) {
        // User clicked a button in ParameterSelector
        // Merge into context
        const detail = event.detail;
        
        // If it's a "confirm scope" action, we send a specific message like "确认" or just re-trigger analysis
        if (detail._confirm_scope) {
             sendMessage("确认选择", true); // Send as user message but triggered programmatically
             return;
        }
        
        // Construct a pseudo-query representing the selection
        let query = "";
        if (detail.kpi) query = `查询 ${detail.kpi}`;
        else if (detail.time_range) query = `时间是 ${detail.time_range}`;
        else if (detail.scope) {
            // Scope update
             // We update the context locally first? 
             // Or send the scope values as text?
             // Backend analyze expects 'query'.
             // But we can also pass updated context directly if we modify analyzeQuery to accept overrides?
             // My analyzeQuery takes 'context'.
             // So I can update `currentContext` here and send a dummy query "update context" or empty.
             
             // However, `analyze` logic relies on extracting entities from query.
             // If I send "product:A", it might extract it.
             // Ideally, I should send "Scope is ..."
             
             // Simplest: Send the values as text.
             query = `筛选条件: ${detail.scope.join(', ')}`;
        }
        
        if (detail._partial) {
             // Just update local context for now? 
             // ParameterSelector handles local state. 
             // If we want to persist it to `currentContext` without triggering AI analysis yet:
             currentContext = { ...currentContext, scope: detail.scope };
             return;
        }
        
        sendMessage(query);
    }
    
    function resetChat() {
        currentContext = {};
        messages = [{
            content: "已重置。请重新提问。",
            isBot: true,
            context: {}
        }];
    }
</script>

<div class="h-full flex flex-col bg-gray-50 max-h-[calc(100vh-64px)]">
    <!-- Header -->
    <div class="bg-white border-b px-4 py-3 flex justify-between items-center shadow-sm shrink-0">
        <h1 class="font-bold text-lg text-gray-800">Rule Bot SQL Assistant</h1>
        <button class="text-sm text-gray-600 hover:text-blue-600" on:click={resetChat}>
            ⟳ 重置对话
        </button>
    </div>
    
    <!-- Chat Area -->
    <div class="flex-1 overflow-y-auto p-4" bind:this={chatContainer}>
        {#each messages as msg}
            <ChatBubble message={msg} isBot={msg.isBot} uiConfig={uiConfig} on:update={handleParamUpdate} />
        {/each}
        
        {#if isLoading}
            <div class="flex w-full justify-start mb-4">
                 <div class="bg-white p-3 rounded-lg border shadow-sm">
                     <span class="animate-pulse">...</span>
                 </div>
            </div>
        {/if}
    </div>
    
    <!-- Input Area -->
    <div class="bg-white border-t p-4 shrink-0">
        <!-- Quick Suggestions (Home Page requirement: "首页：常见问题快捷入口") -->
        {#if messages.length <= 1}
            <div class="flex gap-2 mb-3 overflow-x-auto pb-2">
                <button class="whitespace-nowrap px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm hover:bg-blue-100" on:click={() => sendMessage("查询 headcount")}>
                    查询 Headcount
                </button>
                <button class="whitespace-nowrap px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm hover:bg-blue-100" on:click={() => sendMessage("查询机台数量")}>
                    查询机台数量
                </button>
                 <button class="whitespace-nowrap px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm hover:bg-blue-100" on:click={() => sendMessage("上个月装机工时")}>
                    上个月装机工时
                </button>
            </div>
        {/if}
    
        <div class="flex gap-2">
            <input 
                class="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="输入您的问题..."
                bind:value={userInput}
                on:keydown={(e) => e.key === 'Enter' && sendMessage()}
            />
            <button 
                class="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                on:click={() => sendMessage()}
                disabled={isLoading}
            >
                发送
            </button>
        </div>
    </div>
</div>
