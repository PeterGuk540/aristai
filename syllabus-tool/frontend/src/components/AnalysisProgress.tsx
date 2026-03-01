import React from 'react';

interface AnalysisProgressProps {
  isAnalyzing: boolean;
}

export function AnalysisProgress({ isAnalyzing }: AnalysisProgressProps) {
  // We can simulate steps for better UX since we don't have real-time socket updates yet
  // In a real app, these would be driven by backend events
  const steps = [
    { title: 'Reading Files', description: 'Extracting text and structure from documents', duration: 2000 },
    { title: 'Analyzing Content', description: 'Identifying policies, schedule, and learning goals', duration: 4000 },
    { title: 'Structuring Data', description: 'Formatting content into valid syllabus schema', duration: 3000 },
    { title: 'Finalizing', description: 'Preparing the editor environment', duration: 1000 },
  ];

  const [currentStep, setCurrentStep] = React.useState(0);

  React.useEffect(() => {
    if (!isAnalyzing) {
        setCurrentStep(0);
        return;
    }

    let timer: any;
    let stepIndex = 0;
    
    const runSteps = () => {
        if (stepIndex >= steps.length - 1) return;
        
        timer = setTimeout(() => {
            stepIndex++;
            setCurrentStep(stepIndex);
            runSteps();
        }, steps[stepIndex].duration);
    };

    runSteps();

    return () => clearTimeout(timer);
  }, [isAnalyzing]);

  return (
    <div className="h-full bg-white rounded-lg shadow-sm border border-gray-100 p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-sm space-y-8">
        <div className="text-center">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Processing Documents</h2>
            <p className="text-xs text-gray-500">Extracting content and formatting to schema...</p>
        </div>

        <div className="space-y-6">
            {steps.map((step, index) => {
                const isCompleted = currentStep > index;
                const isCurrent = currentStep === index;

                return (
                    <div key={index} className="flex relative">
                        {/* Line connector */}
                        {index !== steps.length - 1 && (
                            <div className={`absolute top-8 left-3.5 -ml-px h-full w-0.5 ${isCompleted ? 'bg-black' : 'bg-gray-100'}`} aria-hidden="true" />
                        )}

                        <div className="relative flex items-center group">
                            <span className="h-7 w-7 flex items-center justify-center">
                                {isCompleted ? (
                                    <span className="relative z-10 w-6 h-6 flex items-center justify-center bg-black rounded-full">
                                        <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </span>
                                ) : isCurrent ? (
                                    <span className="relative z-10 w-6 h-6 flex items-center justify-center bg-white border border-black rounded-full">
                                        <div className="h-1.5 w-1.5 bg-black rounded-full animate-pulse" />
                                    </span>
                                ) : (
                                    <span className="relative z-10 w-6 h-6 flex items-center justify-center bg-white border border-gray-200 rounded-full">
                                        <span className="h-1.5 w-1.5 bg-gray-200 rounded-full" />
                                    </span>
                                )}
                            </span>
                        </div>
                        <div className="ml-4 min-w-0 flex-1 flex flex-col justify-center">
                            <span className={`text-sm font-medium ${isCurrent || isCompleted ? 'text-gray-900' : 'text-gray-400'}`}>
                                {step.title}
                            </span>
                        </div>
                    </div>
                );
            })}
        </div>
      </div>
    </div>
  );
}
