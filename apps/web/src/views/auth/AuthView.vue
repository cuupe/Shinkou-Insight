<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowRightIcon,
  CheckCircle2Icon,
  EyeIcon,
  EyeOffIcon,
  FingerprintIcon,
  Globe2Icon,
  LoaderCircleIcon,
  LockKeyholeIcon,
  MessageCircleMoreIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
  SparklesIcon,
  UserRoundIcon,
} from '@lucide/vue'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Field, FieldContent, FieldDescription, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type Status = { type: 'success' | 'error' | 'info', message: string }

const route = useRoute()
const router = useRouter()
const activeAuthTab = ref(route.name === 'register' ? 'register' : 'login')
const loginMode = ref('password')
const showPassword = ref(false)
const showRegisterPassword = ref(false)
const showRegisterConfirmPassword = ref(false)
const rememberPassword = ref(false)
const agreed = ref(false)
const registerAgreed = ref(false)
const isSubmitting = ref(false)
const status = ref<Status | null>(null)
const errors = ref<Record<string, string>>({})

const loginAccount = ref('')
const loginPassword = ref('')
const loginPhone = ref('')
const loginSmsCode = ref('')
const loginCaptcha = ref('')
const registerName = ref('')
const registerEmail = ref('')
const registerPassword = ref('')
const registerConfirmPassword = ref('')
const registerCaptcha = ref('')

const captchaCode = ref('K7M8')
const captchaLabel = computed(() => captchaCode.value.split('').join(' '))
const recoveryOpen = ref(false)
const recoveryStep = ref<'account' | 'verify' | 'reset'>('account')
const recoveryAccount = ref('')
const recoveryCode = ref('')
const recoveryCaptcha = ref('')
const recoveryNewPassword = ref('')
const recoveryConfirmPassword = ref('')
const recoveryStatus = ref<Status | null>(null)
const recoveryShowPassword = ref(false)
const agreementOpen = ref(false)
const agreementType = ref<'terms' | 'privacy'>('terms')

const recoveryTitle = computed(() => {
  if (recoveryStep.value === 'verify') return '输入验证码'
  if (recoveryStep.value === 'reset') return '设置新密码'
  return '找回你的密码'
})

watch(() => route.name, (name) => {
  activeAuthTab.value = name === 'register' ? 'register' : 'login'
})

function switchAuthTab(value: string | number) {
  const nextTab = String(value) === 'register' ? 'register' : 'login'
  activeAuthTab.value = nextTab
  status.value = null
  errors.value = {}
  router.push({ name: nextTab })
}

function refreshCaptcha() {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  captchaCode.value = Array.from({ length: 4 }, () => alphabet[Math.floor(Math.random() * alphabet.length)]).join('')
  loginCaptcha.value = ''
  registerCaptcha.value = ''
  recoveryCaptcha.value = ''
}

function isValidCaptcha(value: string) {
  return value.trim().toUpperCase() === captchaCode.value
}

function clearErrors() {
  errors.value = {}
  status.value = null
}

function submitLogin() {
  const nextErrors: Record<string, string> = {}
  if (loginMode.value === 'password') {
    if (!loginAccount.value.trim()) nextErrors.account = '请输入邮箱或手机号'
    if (!loginPassword.value) nextErrors.password = '请输入登录密码'
  } else {
    if (!/^1\d{10}$/.test(loginPhone.value)) nextErrors.phone = '请输入正确的 11 位手机号'
    if (loginSmsCode.value.length !== 6) nextErrors.smsCode = '请输入 6 位短信验证码'
  }
  if (!loginCaptcha.value.trim()) nextErrors.captcha = '请输入图形验证码'
  else if (!isValidCaptcha(loginCaptcha.value)) nextErrors.captcha = '验证码不正确，请重新输入'
  if (!agreed.value) nextErrors.agreement = '请先同意用户协议和隐私政策'
  errors.value = nextErrors
  if (Object.keys(nextErrors).length) return

  isSubmitting.value = true
  window.setTimeout(() => {
    isSubmitting.value = false
    if (rememberPassword.value && loginMode.value === 'password') localStorage.setItem('shinkou-login-account', loginAccount.value)
    else localStorage.removeItem('shinkou-login-account')
    status.value = { type: 'success', message: '登录成功，正在为你打开工作台…' }
  }, 650)
}

function submitRegister() {
  const nextErrors: Record<string, string> = {}
  if (registerName.value.trim().length < 2) nextErrors.name = '请输入至少 2 个字符的姓名'
  if (!/^\S+@\S+\.\S+$/.test(registerEmail.value)) nextErrors.email = '请输入正确的邮箱地址'
  if (registerPassword.value.length < 8) nextErrors.registerPassword = '密码至少需要 8 位字符'
  if (registerPassword.value !== registerConfirmPassword.value) nextErrors.confirmPassword = '两次输入的密码不一致'
  if (!registerCaptcha.value.trim()) nextErrors.registerCaptcha = '请输入图形验证码'
  else if (!isValidCaptcha(registerCaptcha.value)) nextErrors.registerCaptcha = '验证码不正确，请重新输入'
  if (!registerAgreed.value) nextErrors.registerAgreement = '请先同意用户协议和隐私政策'
  errors.value = nextErrors
  if (Object.keys(nextErrors).length) return

  isSubmitting.value = true
  window.setTimeout(() => {
    isSubmitting.value = false
    status.value = { type: 'success', message: '注册成功，请使用新账号登录。' }
    router.push({ name: 'login' })
  }, 650)
}

function openRecovery() {
  recoveryStep.value = 'account'
  recoveryAccount.value = loginAccount.value
  recoveryCode.value = ''
  recoveryCaptcha.value = ''
  recoveryNewPassword.value = ''
  recoveryConfirmPassword.value = ''
  recoveryStatus.value = null
  recoveryShowPassword.value = false
  recoveryOpen.value = true
}

function sendRecoveryCode() {
  const accountValid = /^\S+@\S+\.\S+$/.test(recoveryAccount.value) || /^1\d{10}$/.test(recoveryAccount.value)
  if (!accountValid) {
    recoveryStatus.value = { type: 'error', message: '请输入正确的邮箱或手机号。' }
    return
  }
  if (!isValidCaptcha(recoveryCaptcha.value)) {
    recoveryStatus.value = { type: 'error', message: '图形验证码不正确，请重新输入。' }
    return
  }
  recoveryStep.value = 'verify'
  recoveryStatus.value = { type: 'info', message: '验证码已发送，有效期 5 分钟。' }
}

function verifyRecoveryCode() {
  if (recoveryCode.value.length !== 6) {
    recoveryStatus.value = { type: 'error', message: '请输入 6 位验证码。' }
    return
  }
  recoveryStep.value = 'reset'
  recoveryStatus.value = null
}

function resetRecoveryPassword() {
  if (recoveryNewPassword.value.length < 8) {
    recoveryStatus.value = { type: 'error', message: '新密码至少需要 8 位字符。' }
    return
  }
  if (recoveryNewPassword.value !== recoveryConfirmPassword.value) {
    recoveryStatus.value = { type: 'error', message: '两次输入的新密码不一致。' }
    return
  }
  recoveryStatus.value = { type: 'success', message: '密码已重置，请返回登录。' }
  window.setTimeout(() => {
    recoveryOpen.value = false
    router.push({ name: 'login' })
    status.value = { type: 'success', message: '密码重置成功，请使用新密码登录。' }
  }, 900)
}

function openAgreement(type: 'terms' | 'privacy') {
  agreementType.value = type
  agreementOpen.value = true
}

function sendSmsCode() {
  status.value = { type: 'info', message: '短信验证码已发送，有效期 5 分钟。' }
}

onMounted(() => {
  const rememberedAccount = localStorage.getItem('shinkou-login-account')
  if (rememberedAccount) {
    loginAccount.value = rememberedAccount
    rememberPassword.value = true
  }
})
</script>

<template>
  <main class="auth-page min-h-screen overflow-x-clip px-3 py-3 sm:px-6 sm:py-5 lg:px-10">
    <div class="auth-orb auth-orb-one" />
    <div class="auth-orb auth-orb-two" />
    <div class="relative mx-auto grid min-h-[calc(100svh-1.5rem)] w-full min-w-0 max-w-7xl overflow-hidden rounded-2xl border border-border/70 bg-background/80 shadow-2xl shadow-brand/10 backdrop-blur-xl sm:min-h-[calc(100vh-2.5rem)] sm:rounded-[2rem] lg:grid-cols-[1.02fr_0.98fr]">
      <section class="relative hidden overflow-hidden bg-foreground px-10 py-10 text-background lg:flex lg:flex-col lg:justify-between xl:px-14">
        <div class="auth-grid-pattern pointer-events-none absolute inset-0 opacity-30" />
        <div class="relative">
          <div class="flex items-center gap-3"><div class="grid size-10 place-items-center rounded-2xl bg-brand text-brand-foreground"><SparklesIcon /></div><span class="text-lg font-semibold">Shinkou Insight</span></div>
          <div class="mt-24 max-w-lg"><Badge variant="outline" class="border-background/20 bg-background/10 text-background/80">智能洞察工作台</Badge><h1 class="mt-6 text-5xl font-semibold leading-[1.08] tracking-[-0.05em] xl:text-6xl">让每一个<br /><span class="text-brand">洞察</span> 都有回响。</h1><p class="mt-6 max-w-md text-base leading-7 text-background/60">汇聚你的数据、知识和团队协作，在一个清晰的空间里，把复杂问题变成可执行的下一步。</p></div>
        </div>
        <div class="relative grid gap-4 sm:grid-cols-2"><Card class="border-background/10 bg-background/[0.07] text-background shadow-none"><CardContent class="p-5"><FingerprintIcon class="text-brand" /><p class="mt-7 text-3xl font-semibold">84.6<span class="ml-1 text-sm font-normal text-background/45">分</span></p><p class="mt-1 text-sm text-background/50">本周洞察质量</p></CardContent></Card><Card class="border-background/10 bg-background/[0.07] text-background shadow-none"><CardContent class="p-5"><Globe2Icon class="text-background/75" /><p class="mt-7 text-3xl font-semibold">12.8k<span class="ml-1 text-sm font-normal text-background/45">条</span></p><p class="mt-1 text-sm text-background/50">已沉淀知识</p></CardContent></Card></div>
      </section>

      <section class="flex min-w-0 items-center justify-center px-2 py-6 sm:px-8 sm:py-8 lg:px-12 xl:px-20">
        <div class="w-full min-w-0 max-w-[28rem]">
          <div class="mb-8 flex items-center justify-between lg:hidden"><div class="flex items-center gap-3"><div class="grid size-10 place-items-center rounded-2xl bg-brand text-brand-foreground"><SparklesIcon /></div><span class="font-semibold">Shinkou Insight</span></div><Badge variant="secondary">安全登录</Badge></div>
          <div class="mb-8"><p class="mb-3 text-sm font-medium text-brand">欢迎回来</p><h2 class="text-3xl font-semibold tracking-[-0.04em] sm:text-4xl">进入你的工作台</h2><p class="mt-3 text-sm leading-6 text-muted-foreground">登录后继续查看团队的最新洞察与知识沉淀。</p></div>

          <Tabs v-model="activeAuthTab" class="w-full" @update:model-value="switchAuthTab">
            <TabsList class="mb-7 grid h-11 w-full grid-cols-2 bg-muted/70 p-1"><TabsTrigger value="login">登录</TabsTrigger><TabsTrigger value="register">注册账号</TabsTrigger></TabsList>
            <TabsContent value="login"><Card class="border-border/80 shadow-xl shadow-foreground/[0.04]"><CardHeader class="px-6 pb-4 pt-6 sm:px-7"><CardTitle class="text-xl">登录 Shinkou</CardTitle><CardDescription>使用账号密码或手机号验证码登录</CardDescription></CardHeader><CardContent class="px-6 sm:px-7">
              <Alert v-if="status" class="mb-5" :variant="status.type === 'error' ? 'destructive' : 'default'"><CheckCircle2Icon v-if="status.type === 'success'" /><MessageCircleMoreIcon v-else /><AlertTitle>{{ status.type === 'success' ? '操作成功' : '提示' }}</AlertTitle><AlertDescription>{{ status.message }}</AlertDescription></Alert>
              <Tabs v-model="loginMode"><TabsList variant="line" class="mb-6 w-full justify-start gap-6 rounded-none border-b"><TabsTrigger value="password" class="flex-none px-0">密码登录</TabsTrigger><TabsTrigger value="sms" class="flex-none px-0">验证码登录</TabsTrigger></TabsList>
                <TabsContent value="password"><form class="flex flex-col gap-5" @submit.prevent="submitLogin"><FieldGroup><Field :data-invalid="!!errors.account"><FieldLabel for="login-account">邮箱或手机号</FieldLabel><Input id="login-account" v-model="loginAccount" autocomplete="username" placeholder="name@example.com" :aria-invalid="!!errors.account" @input="clearErrors" /><FieldError v-if="errors.account">{{ errors.account }}</FieldError></Field><Field :data-invalid="!!errors.password"><div class="flex items-center justify-between"><FieldLabel for="login-password">登录密码</FieldLabel><Button type="button" variant="link" class="h-auto p-0 text-xs text-muted-foreground" @click="openRecovery">忘记密码？</Button></div><div class="relative"><Input id="login-password" v-model="loginPassword" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码" class="pr-10" :aria-invalid="!!errors.password" @input="clearErrors" /><Button type="button" variant="ghost" size="icon-sm" class="absolute right-1 top-1/2 -translate-y-1/2" @click="showPassword = !showPassword"><EyeOffIcon v-if="showPassword" /><EyeIcon v-else /></Button></div><FieldError v-if="errors.password">{{ errors.password }}</FieldError></Field></FieldGroup><CaptchaField v-model="loginCaptcha" :code="captchaLabel" :error="errors.captcha" @refresh="refreshCaptcha" /><AgreementField id="login-agreement" v-model="agreed" :error="errors.agreement" @open="openAgreement" /><Field orientation="horizontal" class="items-center gap-2"><Checkbox id="remember-password" v-model="rememberPassword" /><FieldLabel for="remember-password" class="text-xs font-normal text-muted-foreground">记住登录账号</FieldLabel></Field><SubmitButton :loading="isSubmitting">登录</SubmitButton></form></TabsContent>
                <TabsContent value="sms"><form class="flex flex-col gap-5" @submit.prevent="submitLogin"><FieldGroup><Field :data-invalid="!!errors.phone"><FieldLabel for="login-phone">手机号</FieldLabel><Input id="login-phone" v-model="loginPhone" type="tel" placeholder="请输入 11 位手机号" :aria-invalid="!!errors.phone" @input="clearErrors" /><FieldError v-if="errors.phone">{{ errors.phone }}</FieldError></Field><Field :data-invalid="!!errors.smsCode"><FieldLabel for="login-sms-code">短信验证码</FieldLabel><div class="flex gap-2"><InputOTP id="login-sms-code" v-model="loginSmsCode" :maxlength="6" class="min-w-0 flex-1" @input="clearErrors"><InputOTPGroup class="w-full justify-between"><InputOTPSlot v-for="index in 6" :key="index" :index="index - 1" /></InputOTPGroup></InputOTP><Button type="button" variant="outline" class="shrink-0 px-3 text-xs" @click="sendSmsCode">获取验证码</Button></div><FieldDescription>验证码 5 分钟内有效。</FieldDescription><FieldError v-if="errors.smsCode">{{ errors.smsCode }}</FieldError></Field></FieldGroup><CaptchaField v-model="loginCaptcha" :code="captchaLabel" :error="errors.captcha" @refresh="refreshCaptcha" /><AgreementField id="sms-agreement" v-model="agreed" :error="errors.agreement" @open="openAgreement" /><SubmitButton :loading="isSubmitting">登录</SubmitButton></form></TabsContent>
              </Tabs></CardContent><CardFooter class="border-t px-6 pb-6 pt-4 sm:px-7"><div class="flex w-full justify-between text-xs text-muted-foreground"><span class="flex items-center gap-1.5"><ShieldCheckIcon class="text-brand" />数据全程加密</span><span class="flex items-center gap-1.5"><LockKeyholeIcon />安全登录</span></div></CardFooter></Card></TabsContent>

            <TabsContent value="register"><Card class="border-border/80 shadow-xl shadow-foreground/[0.04]"><CardHeader class="px-6 pb-4 pt-6 sm:px-7"><CardTitle class="text-xl">创建你的账号</CardTitle><CardDescription>加入团队，开始沉淀有价值的洞察</CardDescription></CardHeader><CardContent class="px-6 sm:px-7"><form class="flex flex-col gap-5" @submit.prevent="submitRegister"><FieldGroup><Field :data-invalid="!!errors.name"><FieldLabel for="register-name">姓名</FieldLabel><Input id="register-name" v-model="registerName" placeholder="你的姓名" :aria-invalid="!!errors.name" @input="clearErrors" /><FieldError v-if="errors.name">{{ errors.name }}</FieldError></Field><Field :data-invalid="!!errors.email"><FieldLabel for="register-email">工作邮箱</FieldLabel><Input id="register-email" v-model="registerEmail" type="email" placeholder="name@company.com" :aria-invalid="!!errors.email" @input="clearErrors" /><FieldError v-if="errors.email">{{ errors.email }}</FieldError></Field><Field :data-invalid="!!errors.registerPassword"><FieldLabel for="register-password">设置密码</FieldLabel><div class="relative"><Input id="register-password" v-model="registerPassword" :type="showRegisterPassword ? 'text' : 'password'" placeholder="至少 8 位字符" class="pr-10" :aria-invalid="!!errors.registerPassword" @input="clearErrors" /><Button type="button" variant="ghost" size="icon-sm" class="absolute right-1 top-1/2 -translate-y-1/2" @click="showRegisterPassword = !showRegisterPassword"><EyeOffIcon v-if="showRegisterPassword" /><EyeIcon v-else /></Button></div><FieldError v-if="errors.registerPassword">{{ errors.registerPassword }}</FieldError></Field><Field :data-invalid="!!errors.confirmPassword"><FieldLabel for="register-confirm-password">确认密码</FieldLabel><div class="relative"><Input id="register-confirm-password" v-model="registerConfirmPassword" :type="showRegisterConfirmPassword ? 'text' : 'password'" placeholder="再次输入密码" class="pr-10" :aria-invalid="!!errors.confirmPassword" @input="clearErrors" /><Button type="button" variant="ghost" size="icon-sm" class="absolute right-1 top-1/2 -translate-y-1/2" @click="showRegisterConfirmPassword = !showRegisterConfirmPassword"><EyeOffIcon v-if="showRegisterConfirmPassword" /><EyeIcon v-else /></Button></div><FieldError v-if="errors.confirmPassword">{{ errors.confirmPassword }}</FieldError></Field></FieldGroup><CaptchaField v-model="registerCaptcha" :code="captchaLabel" :error="errors.registerCaptcha" @refresh="refreshCaptcha" /><AgreementField id="register-agreement" v-model="registerAgreed" :error="errors.registerAgreement" @open="openAgreement" /><SubmitButton :loading="isSubmitting">创建账号</SubmitButton></form></CardContent><CardFooter class="border-t px-6 pb-6 pt-4 sm:px-7"><p class="flex items-center gap-2 text-xs text-muted-foreground"><UserRoundIcon class="text-brand" />注册后即可邀请团队成员协作</p></CardFooter></Card></TabsContent>
          </Tabs>
          <p class="mt-8 text-center text-xs text-muted-foreground">© 2026 Shinkou Insight · 为团队打造的智能知识空间</p>
        </div>
      </section>
    </div>

    <Dialog v-model:open="recoveryOpen"><DialogContent class="sm:max-w-md"><DialogHeader><DialogTitle>{{ recoveryTitle }}</DialogTitle><DialogDescription v-if="recoveryStep === 'account'">输入绑定的邮箱或手机号，我们会发送验证码帮助你重置密码。</DialogDescription><DialogDescription v-else-if="recoveryStep === 'verify'">验证码已发送至 {{ recoveryAccount }}，请在下方输入。</DialogDescription><DialogDescription v-else>设置一个新的登录密码，完成后即可重新登录。</DialogDescription></DialogHeader><Alert v-if="recoveryStatus" :variant="recoveryStatus.type === 'error' ? 'destructive' : 'default'"><CheckCircle2Icon v-if="recoveryStatus.type === 'success'" /><MessageCircleMoreIcon v-else /><AlertDescription>{{ recoveryStatus.message }}</AlertDescription></Alert><FieldGroup v-if="recoveryStep === 'account'"><Field><FieldLabel for="recovery-account">邮箱或手机号</FieldLabel><Input id="recovery-account" v-model="recoveryAccount" placeholder="name@example.com" /></Field><CaptchaField v-model="recoveryCaptcha" :code="captchaLabel" @refresh="refreshCaptcha" /></FieldGroup><FieldGroup v-else-if="recoveryStep === 'verify'"><Field><FieldLabel for="recovery-code">6 位验证码</FieldLabel><InputOTP id="recovery-code" v-model="recoveryCode" :maxlength="6" class="justify-center"><InputOTPGroup><InputOTPSlot v-for="index in 6" :key="index" :index="index - 1" /></InputOTPGroup></InputOTP><FieldDescription>验证码 5 分钟内有效。</FieldDescription></Field></FieldGroup><FieldGroup v-else><Field><FieldLabel for="recovery-new-password">新密码</FieldLabel><div class="relative"><Input id="recovery-new-password" v-model="recoveryNewPassword" :type="recoveryShowPassword ? 'text' : 'password'" placeholder="至少 8 位字符" class="pr-10" /><Button type="button" variant="ghost" size="icon-sm" class="absolute right-1 top-1/2 -translate-y-1/2" @click="recoveryShowPassword = !recoveryShowPassword"><EyeOffIcon v-if="recoveryShowPassword" /><EyeIcon v-else /></Button></div></Field><Field><FieldLabel for="recovery-confirm-password">确认新密码</FieldLabel><Input id="recovery-confirm-password" v-model="recoveryConfirmPassword" type="password" placeholder="再次输入新密码" /></Field></FieldGroup><DialogFooter><Button type="button" variant="ghost" @click="recoveryOpen = false">取消</Button><Button v-if="recoveryStep === 'account'" type="button" class="bg-brand text-brand-foreground hover:bg-brand/90" @click="sendRecoveryCode">发送验证码</Button><Button v-else-if="recoveryStep === 'verify'" type="button" class="bg-brand text-brand-foreground hover:bg-brand/90" @click="verifyRecoveryCode">验证并继续</Button><Button v-else type="button" class="bg-brand text-brand-foreground hover:bg-brand/90" @click="resetRecoveryPassword">完成重置</Button></DialogFooter></DialogContent></Dialog>

    <Dialog v-model:open="agreementOpen"><DialogContent class="sm:max-w-lg"><DialogHeader><DialogTitle>{{ agreementType === 'privacy' ? '隐私政策' : '用户协议' }}</DialogTitle><DialogDescription>请阅读并了解 Shinkou Insight 的服务约定。</DialogDescription></DialogHeader><div class="max-h-72 overflow-y-auto rounded-xl bg-muted/50 p-4 text-sm leading-7 text-muted-foreground"><p v-if="agreementType === 'privacy'">我们只会收集提供服务所必需的信息，并使用行业标准的技术保护你的账号与工作数据。</p><p v-else>使用 Shinkou Insight 即表示你同意遵守适用法律法规，并对自己创建、上传和分享的内容负责。</p></div><DialogFooter><Button type="button" class="bg-brand text-brand-foreground hover:bg-brand/90" @click="agreementOpen = false">我已了解</Button></DialogFooter></DialogContent></Dialog>
  </main>
</template>

<script lang="ts">
import { defineComponent, h } from 'vue'
import { Button as UiButton } from '@/components/ui/button'
import { Checkbox as UiCheckbox } from '@/components/ui/checkbox'
import { Field as UiField, FieldContent as UiFieldContent, FieldError as UiFieldError, FieldLabel as UiFieldLabel } from '@/components/ui/field'
import { Input as UiInput } from '@/components/ui/input'

export default defineComponent({
  components: {
    CaptchaField: defineComponent({
      props: { modelValue: { type: String, default: '' }, code: { type: String, required: true }, error: { type: String, default: '' } },
      emits: ['update:modelValue', 'refresh'],
      setup(props, { emit }) {
        return () => h('div', { class: 'grid grid-cols-[1fr_auto] items-end gap-3' }, [
          h(UiField, { 'data-invalid': !!props.error }, () => [
            h(UiFieldLabel, { for: 'captcha-input' }, () => '图形验证码'),
            h(UiInput, { id: 'captcha-input', modelValue: props.modelValue, maxlength: 4, placeholder: '输入验证码', 'onUpdate:modelValue': (value: string | number) => emit('update:modelValue', String(value)) }),
            props.error ? h(UiFieldError, null, () => props.error) : null,
          ]),
          h(UiButton, { type: 'button', variant: 'outline', class: 'captcha-tile mb-0.5 h-8 min-w-24 select-none tracking-[0.28em]', onClick: () => emit('refresh') }, () => props.code),
        ])
      },
    }),
    AgreementField: defineComponent({
      props: { modelValue: Boolean, id: { type: String, required: true }, error: { type: String, default: '' } },
      emits: ['update:modelValue', 'open'],
      setup(props, { emit }) {
        return () => h(UiField, { orientation: 'horizontal', 'data-invalid': !!props.error, class: 'items-start gap-2' }, () => [
          h(UiCheckbox, { id: props.id, modelValue: props.modelValue, 'onUpdate:modelValue': (value: boolean | 'indeterminate') => emit('update:modelValue', value === true), class: 'mt-0.5' }),
          h(UiFieldContent, null, () => [
            h(UiFieldLabel, { for: props.id, class: 'text-xs font-normal text-muted-foreground' }, () => [
              '我已阅读并同意 ',
              h(UiButton, { type: 'button', variant: 'link', class: 'h-auto p-0 text-xs text-foreground underline underline-offset-4', onClick: () => emit('open', 'terms') }, () => '用户协议'),
              ' 与 ',
              h(UiButton, { type: 'button', variant: 'link', class: 'h-auto p-0 text-xs text-foreground underline underline-offset-4', onClick: () => emit('open', 'privacy') }, () => '隐私政策'),
            ]),
            props.error ? h(UiFieldError, null, () => props.error) : null,
          ]),
        ])
      },
    }),
    SubmitButton: defineComponent({
      props: { loading: Boolean },
      setup(props, { slots }) {
        return () => h(UiButton, { type: 'submit', disabled: props.loading, class: 'h-11 w-full bg-brand text-brand-foreground shadow-lg shadow-brand/20 hover:bg-brand/90' }, () => [props.loading ? h(LoaderCircleIcon, { class: 'animate-spin', 'data-icon': 'inline-start' }) : h(ArrowRightIcon, { 'data-icon': 'inline-end' }), h('span', null, slots.default?.())])
      },
    }),
  },
})
</script>
