clear;
clc;

%PROBLEM-combustion of liquid ammonia and hydrogen peroxide

%{
ASSUMED:
-infinte chamber lenght

%}
%%
%GIVEN 
hpc_max=98; %maximum hydrogen peroxide concentration [%]
hpc_step=1; %hydrogen peroxide concentration step between max and min in calculations  [%] 
hpc_min=85; %minimum hydrogen peroxide concentration [%]
hpc=hpc_min:hpc_step:hpc_max;

ccp_max=16; %maximum combustion chamber pressure [bar]
ccp_step=1; %combustion chamber pressure step between max and min in calculations  [bar]
ccp_min=10; %minimum combustion chamber pressure [bar]
ccp=ccp_min:ccp_step:ccp_max;
%{
pa_max=1; %maximum atmospheric pressur [bar]
pa_nstep=10; %number of steps of atmospheric pressur between max and min in calculations  [bar]
pa_min=0.01; %minimum atmospheric pressur [bar]
pa=logspace(log10(pa_min),log10(pa_max),pa_nstep);
%}
pr_max=100; %maximum pressure ratio chamber pressure/exhaus pressure [-]
pr_nstep=10; %number of steps of pressure ratio chamber pressure/exhaus pressure between max and min in calculations  [bar]
pr_min=1.01; %minimum pressure ratio chamber pressure/exhaus pressure [-]
pr=logspace(log10(pr_min),log10(pr_max),pr_nstep);

of_max=10; %maximum oxidizer to fuel ratio [-]
of_step=1; %oxidizer to fuel ratio step between max and min in calculations [-]
of_min=1; %minimum oxidizer to fuel ratio [-] 
of=of_min:of_step:of_max;

T_a=239.72; %Liquid ammonia inlet temperature -value foced by CEA [k]
T_hp=280; %hydrogen peroxide inlet temperature -must be bigger than 272.74 [k]
T_w=T_hp; %Water inlet temperature the same as hydrogen peroxide temperature -must be bigger than 273.15 [k]
%%
%CEAM CALCULATIONS
i=1;
for h=hpc
cea(i)=CEA('problem','rocket',... %Problem type-Rocket
        'equilibrium',...%equilibrium flow.  This means that the product composition is allowed to change such that the Gibbs free energy is minimized at every nozzle station.  
        'case','Ammonia and hydrogen peroxide',...%The case name is a file name printed in the output.   
        'p(bar)',ccp,...%Combustion chamber pressure [bar]
        'pi/p',pr,...%pressure ratio chamber pressure/exhaus pressure [-]
        'reactants',...
        'name','H2O2(L)','wt%',h,'t(k)',T_hp,...%hydrogen peroxide is used as oxidant thined with water temperature of 280K was assumed other values are taken from CEA library 
        'name','H2O(L)','wt%',(100.0-h),'t(k)',T_w,...%Water to decrease concentrtion of hydrogen peroxide temperature of 280K the same as hydrogen peroxide other values are taken from CEA library 
        'output','mks','trac',1e-15,...%mks sets allmost SI units; Trace can be used to tighten the convergence value requirement to enhance accuracy for trace product species. 
        'end', 'results');
    i=i+1;
end

%PLOTS
%% Plot 1
%Plot 1-Combustion chamber Temperature vs Oxidant to fuel ratio (for diferent hydrogen peroxide concentration) 
%plot is made for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
pn=1; %position of Combustion chamber pressure in vector "ccp" 
figure('Name','Combustion chamber Temperature vs Oxidant to fuel ratio','NumberTitle','off')
tccPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn)

%% Plot 2

%Plot 2-Specific impulse vs Oxidant to fuel ratio (for different atmospheric pressure) 
%plot is made for hydrogen peroxide concentration number "hpcn" and for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
hpcn=1; %position of hydrogen peroxide concentration in vector "hpc"
pn=1; %position of Combustion chamber pressure in vector "ccp" 

figure('Name','Specific impulse vs Oxidant to fuel ratio','NumberTitle','off')
ispPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)

%% Plot 3

%Plot 3-Cf vs Oxidant to fuel ratio (for different atmospheric pressure) 
%plot is made for hydrogen peroxide concentration number "hpcn" and for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
hpcn=1; %position of hydrogen peroxide concentration in vector "hpc"
pn=1; %position of Combustion chamber pressure in vector "ccp" 

figure('Name','Cf vs Oxidant to fuel ratio','NumberTitle','off')
cfPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)

%% Plot 4

%Plot 4-C* vs Oxidant to fuel ratio (for different atmospheric pressure) 
%plot is made for hydrogen peroxide concentration number "hpcn" and for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
hpcn=1; %position of hydrogen peroxide concentration in vector "hpc"
pn=1; %position of Combustion chamber pressure in vector "ccp" 

figure('Name','C* vs Oxidant to fuel ratio','NumberTitle','off')
cstarPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)

%% Plot 5

%Plot 5-Cp vs Oxidant to fuel ratio (for different atmospheric pressure) 
%plot is made for hydrogen peroxide concentration number "hpcn" and for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
hpcn=1; %position of hydrogen peroxide concentration in vector "hpc"
pn=1; %position of Combustion chamber pressure in vector "ccp" 

figure('Name','Cp vs Oxidant to fuel ratio','NumberTitle','off')
cpPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)


%% Plot 6

%Plot 6-γ vs Oxidant to fuel ratio (for different atmospheric pressure) 
%plot is made for hydrogen peroxide concentration number "hpcn" and for Combustion chamber pressure number "pn" as Combustion chamber Temperature dont change much with pressure 
hpcn=1; %position of hydrogen peroxide concentration in vector "hpc"
pn=1; %position of Combustion chamber pressure in vector "ccp" 

figure('Name','γ vs Oxidant to fuel ratio','NumberTitle','off')
gammaPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)


%% PLOT FUNCTIONS
function tccPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) tccPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value'))) )
 

ax = gca;
ax.OuterPosition= [0 0.2 1 0.8];
ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('Tcc [K]')
title({['Combustion chamber Temperature vs Oxidant to fuel ratio']
    ['for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
hold all
i=1;
plot(of,cea(i).output.eql.temperature(:,pn,1),'o','MarkerEdgeColor','black','DisplayName','Calculated points')
for h=hpc
    
ofq1=of_min:of_step/10:of_max;
Tcc_i=spline(of,cea(i).output.eql.temperature(:,pn,1),ofq1);

plot(of,cea(i).output.eql.temperature(:,pn,1),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,Tcc_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['hpc= ',num2str(hpc(i)),'% interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold on
end

function ispPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) ispPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value')), hpcn) )
 
 SliderHPC = uicontrol('Style','slider','Position',[81,15,419,20],...
             'value',hpcn, 'min',1, 'max',hpc_size(2),'SliderStep', [1/(hpc_size(2)-1) 1/(hpc_size(2)-1)]);
         
 TextHPC = uicontrol('Style','text','Position',[30,15,50,20],...
                'String','HPC [%]');         
         
set(SliderHPC,'Callback',@(hObject,eventdata) ispPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn,  nearest(get(hObject,'Value'))) )
        


ax = gca;
ax.OuterPosition= [0 0.2 1 0.8];
ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('Isp [s]')
title({['Specific impulse vs Oxidant to fuel ratio']
    ['for hydrogen peroxide concentration=',num2str(hpc(hpcn)),' %']
    ['and for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
hold on
i=3;
plot(of,cea(hpcn).output.eql.isp(:,pn,i),'o','MarkerEdgeColor','black','DisplayName','Calculated points')
for h=pr
    
ofq1=of_min:of_step/10:of_max;
isp_i=spline(of,cea(hpcn).output.eql.isp(:,pn,i),ofq1);

plot(of,cea(hpcn).output.eql.isp(:,pn,i),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,isp_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['pa= ',num2str(ccp(pn)/pr(i-2)),'Pa interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold off

end

function cfPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) cfPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value')), hpcn) )
 
 SliderHPC = uicontrol('Style','slider','Position',[81,15,419,20],...
             'value',hpcn, 'min',1, 'max',hpc_size(2),'SliderStep', [1/(hpc_size(2)-1) 1/(hpc_size(2)-1)]);
         
 TextHPC = uicontrol('Style','text','Position',[30,15,50,20],...
                'String','HPC [%]');         
         
set(SliderHPC,'Callback',@(hObject,eventdata) cfPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn,  nearest(get(hObject,'Value'))) )
        


ax = gca;
ax.OuterPosition= [0 0.2 1 0.8];
ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('Cf [-]')
title({['Cf vs Oxidant to fuel ratio']
    ['for hydrogen peroxide concentration=',num2str(hpc(hpcn)),' %']
    ['and for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
hold on
i=3;
plot(of,cea(hpcn).output.eql.cf(:,pn,i),'o','MarkerEdgeColor','black','DisplayName','Calculated points')
for h=pr
    
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.cf(:,pn,i),ofq1);

plot(of,cea(hpcn).output.eql.cf(:,pn,i),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['pa= ',num2str(ccp(pn)/pr(i-2)),'Pa interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold off

end

function cstarPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) cstarPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value')), hpcn) )
 
ax = gca;
ax.OuterPosition= [0 0.2 1 0.8];
ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('C* [m/s]')
title({['C* vs Oxidant to fuel ratio']
    ['and for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
hold on
i=1;
plot(of,cea(i).output.eql.cstar(:,pn,1),'o','MarkerEdgeColor','black','DisplayName','Calculated points')
for h=hpc
    
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(i).output.eql.cstar(:,pn,1),ofq1);

plot(of,cea(i).output.eql.cstar(:,pn,1),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['hpc= ',num2str(hpc(i)),'% interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold off

end

function cpPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) cpPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value')), hpcn) )
 
 SliderHPC = uicontrol('Style','slider','Position',[81,15,419,20],...
             'value',hpcn, 'min',1, 'max',hpc_size(2),'SliderStep', [1/(hpc_size(2)-1) 1/(hpc_size(2)-1)]);
         
 TextHPC = uicontrol('Style','text','Position',[30,15,50,20],...
                'String','HPC [%]');         
         
set(SliderHPC,'Callback',@(hObject,eventdata) cpPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn,  nearest(get(hObject,'Value'))) )
        


ax = gca;
ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('Cp [J/K]')
title({['Cp vs Oxidant to fuel ratio']
    ['for hydrogen peroxide concentration=',num2str(hpc(hpcn)),' %']
    ['and for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
ax.OuterPosition= [0 0.2 1 0.8];
hold on

i=3;
plot(of,cea(hpcn).output.eql.cp(:,pn,i),'o','MarkerEdgeColor','black','DisplayName','Calculated points')

%combustion chamber
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.cp(:,pn,1),ofq1);

plot(of,cea(hpcn).output.eql.cp(:,pn,1),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['Combustion chamber-interpolated'])

%throat
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.cp(:,pn,2),ofq1);

plot(of,cea(hpcn).output.eql.cp(:,pn,2),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['Throat-interpolated'])

for h=pr
    
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.cp(:,pn,i),ofq1);

plot(of,cea(hpcn).output.eql.cp(:,pn,i),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['pa= ',num2str(ccp(pn)/pr(i-2)),'Pa interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold off

end

function gammaPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn, hpcn)
clf
ccp_size=size(ccp);
SliderCCP = uicontrol('Style','slider','Position',[81,50,419,20],...
             'value',pn, 'min',1, 'max',ccp_size(2),'SliderStep', [1/(ccp_size(2)-1) 1/(ccp_size(2)-1)]);
         
 TextCCP = uicontrol('Style','text','Position',[30,50,50,20],...
                'String','CCP [bar]');
 hpc_size=size(hpc);
set(SliderCCP,'Callback',@(hObject,eventdata) gammaPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr,  nearest(get(hObject,'Value')), hpcn) )
 
 SliderHPC = uicontrol('Style','slider','Position',[81,15,419,20],...
             'value',hpcn, 'min',1, 'max',hpc_size(2),'SliderStep', [1/(hpc_size(2)-1) 1/(hpc_size(2)-1)]);
         
 TextHPC = uicontrol('Style','text','Position',[30,15,50,20],...
                'String','HPC [%]');         
         
set(SliderHPC,'Callback',@(hObject,eventdata) gammaPlot(hpc, ccp, cea, of, of_min, of_max, of_step, pr, pn,  nearest(get(hObject,'Value'))) )
        
ax = gca;

ax.XAxisLocation = 'origin';
%ax.XLim=[0 (Lg2+Ls+Lg1)];
%yticks(-2:1:4.5);
%ax.YLim=[-2 4.5];
xlabel('o/f [-]')
ylabel('γ [-]')
title({['γ vs Oxidant to fuel ratio']
    ['for hydrogen peroxide concentration=',num2str(hpc(hpcn)),' %']
    ['and for Combustion chamber pressure=',num2str(ccp(pn)),' bar']})
ax.XColor = 'black';
hold on
ax.OuterPosition= [0 0.2 1 0.8];
i=3;
plot(of,cea(hpcn).output.eql.gamma(:,pn,i),'o','MarkerEdgeColor','black','DisplayName','Calculated points')

%combustion chamber
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.gamma(:,pn,1),ofq1);

plot(of,cea(hpcn).output.eql.gamma(:,pn,1),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['Combustion chamber-interpolated'])

%throat
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.gamma(:,pn,2),ofq1);

plot(of,cea(hpcn).output.eql.gamma(:,pn,2),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['Throat-interpolated'])

for h=pr
    
ofq1=of_min:of_step/10:of_max;
of_i=spline(of,cea(hpcn).output.eql.gamma(:,pn,i),ofq1);

plot(of,cea(hpcn).output.eql.gamma(:,pn,i),'o','MarkerEdgeColor','black','HandleVisibility','off')
plot(ofq1,of_i,'color',rand(1,3), 'LineWidth', 1,'DisplayName',['pa= ',num2str(ccp(pn)/pr(i-2)),'Pa interpolated'])

i=i+1;
end
lgd = legend;
legend('Location','eastoutside');
hold off

end

