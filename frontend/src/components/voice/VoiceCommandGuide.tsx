'use client';

import { useState } from 'react';
import { X, Mic, Navigation, Settings, FileText, MessageSquare, BarChart, Users, Play, CheckCircle, Moon, LogOut, Brain, HelpCircle, FolderOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { useLanguage } from '@/lib/i18n-provider';

interface VoiceCommandGuideProps {
  onClose: () => void;
}

interface CommandCategory {
  id: string;
  labelKey: string;
  icon: React.ElementType;
  descriptionKey: string;
  commands: {
    phraseEn: string;
    phraseEs: string;
    alternativesEn?: string[];
    alternativesEs?: string[];
    descriptionKey: string;
  }[];
}

const commandCategories: CommandCategory[] = [
  {
    id: 'navigation',
    labelKey: 'voiceGuide.categories.navigation',
    icon: Navigation,
    descriptionKey: 'voiceGuide.descriptions.navigation',
    commands: [
      {
        phraseEn: '"Go to courses"',
        phraseEs: '"Ir a cursos"',
        alternativesEn: ['"Open courses"', '"Courses page"'],
        alternativesEs: ['"Abrir cursos"', '"Mostrar mis cursos"'],
        descriptionKey: 'voiceGuide.commands.goToCourses'
      },
      {
        phraseEn: '"Go to sessions"',
        phraseEs: '"Ir a sesiones"',
        alternativesEn: ['"Open sessions"', '"Sessions page"'],
        alternativesEs: ['"Abrir sesiones"', '"Mostrar sesiones"'],
        descriptionKey: 'voiceGuide.commands.goToSessions'
      },
      {
        phraseEn: '"Go to forum"',
        phraseEs: '"Ir al foro"',
        alternativesEn: ['"Open forum"', '"Forum page"'],
        alternativesEs: ['"Abrir el foro"', '"Ver las discusiones"'],
        descriptionKey: 'voiceGuide.commands.goToForum'
      },
      {
        phraseEn: '"Go to console"',
        phraseEs: '"Ir a la consola"',
        alternativesEn: ['"Open console"', '"Console page"'],
        alternativesEs: ['"Abrir la consola"', '"Quiero usar la consola"'],
        descriptionKey: 'voiceGuide.commands.goToConsole'
      },
      {
        phraseEn: '"Go to reports"',
        phraseEs: '"Ir a reportes"',
        alternativesEn: ['"Open reports"', '"Reports page"'],
        alternativesEs: ['"Abrir reportes"', '"Ver los informes"'],
        descriptionKey: 'voiceGuide.commands.goToReports'
      },
    ],
  },
  {
    id: 'courses',
    labelKey: 'voiceGuide.categories.courses',
    icon: FileText,
    descriptionKey: 'voiceGuide.descriptions.courses',
    commands: [
      {
        phraseEn: '"Create a course"',
        phraseEs: '"Crear un curso"',
        alternativesEn: ['"New course"', '"Make a course"'],
        alternativesEs: ['"Nuevo curso"', '"Hacer un curso"'],
        descriptionKey: 'voiceGuide.commands.createCourse'
      },
      {
        phraseEn: '"Generate"',
        phraseEs: '"Generar"',
        alternativesEn: ['"Generate syllabus"', '"AI help"'],
        alternativesEs: ['"Generar programa"', '"Ayuda de IA"'],
        descriptionKey: 'voiceGuide.commands.generate'
      },
      {
        phraseEn: '"Yes" / "Use it"',
        phraseEs: '"Sí" / "Usar esto"',
        alternativesEn: ['"Looks good"', '"Accept"'],
        alternativesEs: ['"Se ve bien"', '"Aceptar"'],
        descriptionKey: 'voiceGuide.commands.acceptGenerated'
      },
      {
        phraseEn: '"No" / "Edit"',
        phraseEs: '"No" / "Editar"',
        alternativesEn: ['"Let me edit"', '"I\'ll dictate"'],
        alternativesEs: ['"Déjame editar"', '"Voy a dictar"'],
        descriptionKey: 'voiceGuide.commands.declineGenerated'
      },
      {
        phraseEn: '"Select first course"',
        phraseEs: '"Seleccionar primer curso"',
        alternativesEn: ['"Choose first course"', '"Open first course"'],
        alternativesEs: ['"Elegir primer curso"', '"Abrir primer curso"'],
        descriptionKey: 'voiceGuide.commands.selectFirstCourse'
      },
    ],
  },
  {
    id: 'sessions',
    labelKey: 'voiceGuide.categories.sessions',
    icon: Play,
    descriptionKey: 'voiceGuide.descriptions.sessions',
    commands: [
      {
        phraseEn: '"Go to manage status tab"',
        phraseEs: '"Ir a pestaña de estado"',
        alternativesEn: ['"Manage status"', '"Status tab"'],
        alternativesEs: ['"Gestionar estado"', '"Pestaña de estado"'],
        descriptionKey: 'voiceGuide.commands.manageStatus'
      },
      {
        phraseEn: '"View materials"',
        phraseEs: '"Ver materiales"',
        alternativesEn: ['"Show materials"', '"Open materials"', '"Course materials"'],
        alternativesEs: ['"Mostrar materiales"', '"Abrir materiales"', '"Materiales del curso"'],
        descriptionKey: 'voiceGuide.commands.viewMaterials'
      },
      {
        phraseEn: '"Go live"',
        phraseEs: '"Iniciar en vivo"',
        alternativesEn: ['"Start session"', '"Make it live"', '"Launch session"'],
        alternativesEs: ['"Comenzar sesión"', '"Poner en vivo"', '"Activar sesión"'],
        descriptionKey: 'voiceGuide.commands.goLive'
      },
      {
        phraseEn: '"Set to draft"',
        phraseEs: '"Poner en borrador"',
        alternativesEn: ['"Make it draft"', '"Revert to draft"'],
        alternativesEs: ['"Cambiar a borrador"', '"Volver a borrador"'],
        descriptionKey: 'voiceGuide.commands.setToDraft'
      },
      {
        phraseEn: '"Complete"',
        phraseEs: '"Completar"',
        alternativesEn: ['"End session"', '"Finish session"', '"Mark complete"'],
        alternativesEs: ['"Terminar sesión"', '"Finalizar sesión"', '"Marcar completada"'],
        descriptionKey: 'voiceGuide.commands.completeSession'
      },
      {
        phraseEn: '"Schedule"',
        phraseEs: '"Programar"',
        alternativesEn: ['"Schedule session"', '"Set to scheduled"'],
        alternativesEs: ['"Programar sesión"', '"Agendar sesión"'],
        descriptionKey: 'voiceGuide.commands.scheduleSession'
      },
    ],
  },
  {
    id: 'materials',
    labelKey: 'voiceGuide.categories.materials',
    icon: FolderOpen,
    descriptionKey: 'voiceGuide.descriptions.materials',
    commands: [
      {
        phraseEn: '"View materials"',
        phraseEs: '"Ver materiales"',
        alternativesEn: ['"Show materials"', '"Open materials"'],
        alternativesEs: ['"Mostrar materiales"', '"Abrir materiales"'],
        descriptionKey: 'voiceGuide.commands.viewMaterials'
      },
      {
        phraseEn: '"Show course files"',
        phraseEs: '"Mostrar archivos del curso"',
        alternativesEn: ['"View documents"', '"Course readings"'],
        alternativesEs: ['"Ver documentos"', '"Lecturas del curso"'],
        descriptionKey: 'voiceGuide.commands.showCourseFiles'
      },
    ],
  },
  {
    id: 'forum',
    labelKey: 'voiceGuide.categories.forum',
    icon: MessageSquare,
    descriptionKey: 'voiceGuide.descriptions.forum',
    commands: [
      {
        phraseEn: '"Go to cases tab"',
        phraseEs: '"Ir a pestaña de casos"',
        alternativesEn: ['"Cases"', '"Case studies"'],
        alternativesEs: ['"Casos"', '"Casos de estudio"'],
        descriptionKey: 'voiceGuide.commands.goToCases'
      },
      {
        phraseEn: '"Go to discussion tab"',
        phraseEs: '"Ir a discusión"',
        alternativesEn: ['"Discussion"', '"Discussions"'],
        alternativesEs: ['"Discusiones"', '"Ver discusión"'],
        descriptionKey: 'voiceGuide.commands.goToDiscussion'
      },
      {
        phraseEn: '"Post to discussion"',
        phraseEs: '"Publicar en discusión"',
        alternativesEn: ['"New post"', '"Create post"'],
        alternativesEs: ['"Nueva publicación"', '"Crear publicación"'],
        descriptionKey: 'voiceGuide.commands.postToDiscussion'
      },
      {
        phraseEn: '"Post a case"',
        phraseEs: '"Publicar un caso"',
        alternativesEn: ['"Create case study"', '"New case"'],
        alternativesEs: ['"Crear caso de estudio"', '"Nuevo caso"'],
        descriptionKey: 'voiceGuide.commands.postCase'
      },
    ],
  },
  {
    id: 'console',
    labelKey: 'voiceGuide.categories.console',
    icon: Settings,
    descriptionKey: 'voiceGuide.descriptions.console',
    commands: [
      {
        phraseEn: '"Go to copilot tab"',
        phraseEs: '"Ir a copilot"',
        alternativesEn: ['"AI copilot"', '"Copilot"'],
        alternativesEs: ['"Copilot IA"', '"Asistente"'],
        descriptionKey: 'voiceGuide.commands.goToCopilot'
      },
      {
        phraseEn: '"Start copilot"',
        phraseEs: '"Iniciar copilot"',
        alternativesEn: ['"Activate copilot"', '"Turn on copilot"'],
        alternativesEs: ['"Activar copilot"', '"Encender copilot"'],
        descriptionKey: 'voiceGuide.commands.startCopilot'
      },
      {
        phraseEn: '"Stop copilot"',
        phraseEs: '"Detener copilot"',
        alternativesEn: ['"Deactivate copilot"', '"Turn off copilot"'],
        alternativesEs: ['"Desactivar copilot"', '"Apagar copilot"'],
        descriptionKey: 'voiceGuide.commands.stopCopilot'
      },
      {
        phraseEn: '"Refresh interventions"',
        phraseEs: '"Actualizar intervenciones"',
        alternativesEn: ['"Update interventions"', '"Get interventions"'],
        alternativesEs: ['"Refrescar intervenciones"', '"Ver intervenciones"'],
        descriptionKey: 'voiceGuide.commands.refreshInterventions'
      },
      {
        phraseEn: '"Create a poll"',
        phraseEs: '"Crear una encuesta"',
        alternativesEn: ['"New poll"', '"Make a poll"'],
        alternativesEs: ['"Nueva encuesta"', '"Hacer una pregunta"'],
        descriptionKey: 'voiceGuide.commands.createPoll'
      },
    ],
  },
  {
    id: 'reports',
    labelKey: 'voiceGuide.categories.reports',
    icon: BarChart,
    descriptionKey: 'voiceGuide.descriptions.reports',
    commands: [
      {
        phraseEn: '"Refresh report"',
        phraseEs: '"Actualizar reporte"',
        alternativesEn: ['"Reload report"', '"Update report"'],
        alternativesEs: ['"Refrescar reporte"', '"Recargar informe"'],
        descriptionKey: 'voiceGuide.commands.refreshReport'
      },
      {
        phraseEn: '"Regenerate report"',
        phraseEs: '"Regenerar reporte"',
        alternativesEn: ['"Generate new report"', '"Rebuild report"'],
        alternativesEs: ['"Generar nuevo reporte"', '"Crear nuevo informe"'],
        descriptionKey: 'voiceGuide.commands.regenerateReport'
      },
    ],
  },
  {
    id: 'ai-generation',
    labelKey: 'voiceGuide.categories.aiGeneration',
    icon: Brain,
    descriptionKey: 'voiceGuide.descriptions.aiGeneration',
    commands: [
      {
        phraseEn: '"Generate"',
        phraseEs: '"Generar"',
        alternativesEn: ['"Generate syllabus"', '"AI help"', '"Create for me"'],
        alternativesEs: ['"Generar programa"', '"Ayuda de IA"', '"Crear para mí"'],
        descriptionKey: 'voiceGuide.commands.generateContent'
      },
      {
        phraseEn: '"Yes, use it"',
        phraseEs: '"Sí, usar esto"',
        alternativesEn: ['"Looks good"', '"Accept"', '"Use this"'],
        alternativesEs: ['"Se ve bien"', '"Aceptar"', '"Usar"'],
        descriptionKey: 'voiceGuide.commands.acceptAIContent'
      },
      {
        phraseEn: '"No, let me edit"',
        phraseEs: '"No, déjame editar"',
        alternativesEn: ['"I\'ll dictate"', '"Manual"'],
        alternativesEs: ['"Voy a dictar"', '"Manual"'],
        descriptionKey: 'voiceGuide.commands.declineAIContent'
      },
    ],
  },
  {
    id: 'intelligence',
    labelKey: 'voiceGuide.categories.intelligence',
    icon: HelpCircle,
    descriptionKey: 'voiceGuide.descriptions.intelligence',
    commands: [
      {
        phraseEn: '"How\'s the class doing?"',
        phraseEs: '"¿Cómo va la clase?"',
        alternativesEn: ['"Class status"', '"Quick update"', '"Session overview"'],
        alternativesEs: ['"Estado de la clase"', '"Actualización rápida"', '"Resumen de sesión"'],
        descriptionKey: 'voiceGuide.commands.classStatus'
      },
      {
        phraseEn: '"Who needs help?"',
        phraseEs: '"¿Quién necesita ayuda?"',
        alternativesEn: ['"Struggling students"', '"Who\'s behind?"'],
        alternativesEs: ['"Estudiantes con dificultades"', '"¿Quién está atrasado?"'],
        descriptionKey: 'voiceGuide.commands.whoNeedsHelp'
      },
      {
        phraseEn: '"What were the misconceptions?"',
        phraseEs: '"¿Cuáles fueron los errores?"',
        alternativesEn: ['"Common mistakes"', '"What did students get wrong?"'],
        alternativesEs: ['"Errores comunes"', '"¿Qué respondieron mal?"'],
        descriptionKey: 'voiceGuide.commands.misconceptions'
      },
      {
        phraseEn: '"How did students score?"',
        phraseEs: '"¿Cómo les fue a los estudiantes?"',
        alternativesEn: ['"Student scores"', '"Class performance"'],
        alternativesEs: ['"Puntuaciones"', '"Desempeño de la clase"'],
        descriptionKey: 'voiceGuide.commands.studentScores'
      },
      {
        phraseEn: '"Summarize the discussion"',
        phraseEs: '"Resumir la discusión"',
        alternativesEn: ['"Discussion summary"', '"Key themes"'],
        alternativesEs: ['"Resumen de discusión"', '"Temas clave"'],
        descriptionKey: 'voiceGuide.commands.summarizeDiscussion'
      },
    ],
  },
  {
    id: 'dropdowns',
    labelKey: 'voiceGuide.categories.dropdowns',
    icon: Users,
    descriptionKey: 'voiceGuide.descriptions.dropdowns',
    commands: [
      {
        phraseEn: '"Select first"',
        phraseEs: '"Seleccionar primero"',
        alternativesEn: ['"First option"', '"Choose first"'],
        alternativesEs: ['"Primera opción"', '"Elegir primero"'],
        descriptionKey: 'voiceGuide.commands.selectFirst'
      },
      {
        phraseEn: '"Select second"',
        phraseEs: '"Seleccionar segundo"',
        alternativesEn: ['"Second option"', '"Choose second"'],
        alternativesEs: ['"Segunda opción"', '"Elegir segundo"'],
        descriptionKey: 'voiceGuide.commands.selectSecond'
      },
      {
        phraseEn: '"Select [name]"',
        phraseEs: '"Seleccionar [nombre]"',
        alternativesEn: ['"Choose [name]"'],
        alternativesEs: ['"Elegir [nombre]"'],
        descriptionKey: 'voiceGuide.commands.selectByName'
      },
      {
        phraseEn: '"Cancel"',
        phraseEs: '"Cancelar"',
        alternativesEn: ['"Never mind"', '"Go back"', '"Stop"'],
        alternativesEs: ['"No importa"', '"Volver"', '"Detener"'],
        descriptionKey: 'voiceGuide.commands.cancel'
      },
      {
        phraseEn: '"Skip"',
        phraseEs: '"Saltar"',
        alternativesEn: ['"Next"', '"Pass"'],
        alternativesEs: ['"Siguiente"', '"Pasar"'],
        descriptionKey: 'voiceGuide.commands.skip'
      },
    ],
  },
  {
    id: 'forms',
    labelKey: 'voiceGuide.categories.forms',
    icon: CheckCircle,
    descriptionKey: 'voiceGuide.descriptions.forms',
    commands: [
      {
        phraseEn: '[Speak your answer]',
        phraseEs: '[Dicta tu respuesta]',
        descriptionKey: 'voiceGuide.commands.dictateAnswer'
      },
      {
        phraseEn: '"Yes"',
        phraseEs: '"Sí"',
        alternativesEn: ['"Yeah"', '"Sure"', '"Okay"'],
        alternativesEs: ['"Claro"', '"Okay"', '"De acuerdo"'],
        descriptionKey: 'voiceGuide.commands.confirm'
      },
      {
        phraseEn: '"No"',
        phraseEs: '"No"',
        alternativesEn: ['"Nope"', '"No thanks"'],
        alternativesEs: ['"No gracias"', '"Cancelar"'],
        descriptionKey: 'voiceGuide.commands.decline'
      },
      {
        phraseEn: '"That\'s enough"',
        phraseEs: '"Es suficiente"',
        alternativesEn: ['"Done"', '"Finish"', '"No more"'],
        alternativesEs: ['"Listo"', '"Terminar"', '"No más"'],
        descriptionKey: 'voiceGuide.commands.finishAdding'
      },
      {
        phraseEn: '"Submit"',
        phraseEs: '"Enviar"',
        alternativesEn: ['"Confirm"', '"Send"'],
        alternativesEs: ['"Confirmar"', '"Mandar"'],
        descriptionKey: 'voiceGuide.commands.submit'
      },
    ],
  },
  {
    id: 'theme',
    labelKey: 'voiceGuide.categories.theme',
    icon: Moon,
    descriptionKey: 'voiceGuide.descriptions.theme',
    commands: [
      {
        phraseEn: '"Dark mode"',
        phraseEs: '"Modo oscuro"',
        alternativesEn: ['"Switch to dark"', '"Enable dark mode"'],
        alternativesEs: ['"Cambiar a oscuro"', '"Activar modo oscuro"'],
        descriptionKey: 'voiceGuide.commands.darkMode'
      },
      {
        phraseEn: '"Light mode"',
        phraseEs: '"Modo claro"',
        alternativesEn: ['"Switch to light"', '"Enable light mode"'],
        alternativesEs: ['"Cambiar a claro"', '"Activar modo claro"'],
        descriptionKey: 'voiceGuide.commands.lightMode'
      },
      {
        phraseEn: '"Open menu"',
        phraseEs: '"Abrir menú"',
        alternativesEn: ['"Account menu"', '"My account"'],
        alternativesEs: ['"Menú de cuenta"', '"Mi cuenta"'],
        descriptionKey: 'voiceGuide.commands.openMenu'
      },
      {
        phraseEn: '"View voice guide"',
        phraseEs: '"Ver guía de voz"',
        alternativesEn: ['"Voice commands"', '"Show commands"'],
        alternativesEs: ['"Comandos de voz"', '"Mostrar comandos"'],
        descriptionKey: 'voiceGuide.commands.viewVoiceGuide'
      },
      {
        phraseEn: '"Sign out"',
        phraseEs: '"Cerrar sesión"',
        alternativesEn: ['"Log out"', '"Logout"'],
        alternativesEs: ['"Salir"', '"Desconectar"'],
        descriptionKey: 'voiceGuide.commands.signOut'
      },
      {
        phraseEn: '"Got it"',
        phraseEs: '"Entendido"',
        alternativesEn: ['"Okay"', '"Done"', '"Close"'],
        alternativesEs: ['"Okay"', '"Listo"', '"Cerrar"'],
        descriptionKey: 'voiceGuide.commands.gotIt'
      },
    ],
  },
];

export function VoiceCommandGuide({ onClose }: VoiceCommandGuideProps) {
  const [activeCategory, setActiveCategory] = useState('navigation');
  const activeCommands = commandCategories.find(c => c.id === activeCategory);
  const t = useTranslations();
  const { locale } = useLanguage();
  const isSpanish = locale === 'es';

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-primary-100 dark:bg-primary-900/30 rounded-full flex items-center justify-center">
              <Mic className="h-6 w-6 text-primary-600 dark:text-primary-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                {t('voice.voiceGuide')}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {t('voiceGuide.subtitle')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            data-voice-id="close-voice-guide"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Sidebar - Category List */}
          <div className="w-56 border-r border-gray-200 dark:border-gray-700 overflow-y-auto flex-shrink-0">
            <nav className="p-2">
              {commandCategories.map((category) => {
                const Icon = category.icon;
                return (
                  <button
                    key={category.id}
                    onClick={() => setActiveCategory(category.id)}
                    className={cn(
                      'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors text-left',
                      activeCategory === category.id
                        ? 'bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300'
                        : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                    )}
                  >
                    <Icon className="h-4 w-4 flex-shrink-0" />
                    <span className="truncate">{t(category.labelKey)}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Main Content - Commands */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeCommands && (
              <div>
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    {t(activeCommands.labelKey)}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {t(activeCommands.descriptionKey)}
                  </p>
                </div>
                <div className="space-y-4">
                  {activeCommands.commands.map((cmd, index) => {
                    const phrase = isSpanish ? cmd.phraseEs : cmd.phraseEn;
                    const alternatives = isSpanish ? cmd.alternativesEs : cmd.alternativesEn;

                    return (
                      <div
                        key={index}
                        className="p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600"
                      >
                        <div className="flex flex-wrap items-start gap-2 mb-2">
                          <code className="px-3 py-1 bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300 rounded-md text-sm font-mono">
                            {phrase}
                          </code>
                          {alternatives && alternatives.map((alt, altIndex) => (
                            <code
                              key={altIndex}
                              className="px-2 py-1 bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded-md text-xs font-mono"
                            >
                              {alt}
                            </code>
                          ))}
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {t(cmd.descriptionKey)}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Tips Footer */}
        <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border-t border-gray-200 dark:border-gray-700">
          <div className="text-sm">
            <p className="font-medium text-blue-900 dark:text-blue-100 mb-1">{t('voice.tips')}:</p>
            <ul className="text-blue-700 dark:text-blue-300 space-y-1">
              <li>- {t('voice.tipNatural')}</li>
              <li>- {t('voice.tipWait')}</li>
              <li>- {t('voice.tipCancel')}</li>
              <li>- {t('voice.tipLocation')}</li>
            </ul>
            <p className="font-medium text-blue-900 dark:text-blue-100 mt-3 mb-1">{t('voiceGuide.aiInsights')}:</p>
            <ul className="text-blue-700 dark:text-blue-300 space-y-1">
              <li>- {t('voiceGuide.tipClassStatus')}</li>
              <li>- {t('voiceGuide.tipWhoNeedsHelp')}</li>
              <li>- {t('voiceGuide.tipCopilotSuggestions')}</li>
              <li>- {t('voiceGuide.tipSpecificStudent')}</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg transition-colors"
            data-voice-id="got-it-voice-guide"
          >
            {t('voiceGuide.gotIt')}
          </button>
        </div>
      </div>
    </div>
  );
}
