function varargout = GUI_Taylor_Maccoll(varargin)

% Begin initialization code - DO NOT EDIT
gui_Singleton = 1;
gui_State = struct('gui_Name',       mfilename, ...
                   'gui_Singleton',  gui_Singleton, ...
                   'gui_OpeningFcn', @GUI_Taylor_Maccoll_OpeningFcn, ...
                   'gui_OutputFcn',  @GUI_Taylor_Maccoll_OutputFcn, ...
                   'gui_LayoutFcn',  [] , ...
                   'gui_Callback',   []);
if nargin && ischar(varargin{1})
    gui_State.gui_Callback = str2func(varargin{1});
end

if nargout
    [varargout{1:nargout}] = gui_mainfcn(gui_State, varargin{:});
else
    gui_mainfcn(gui_State, varargin{:});
end
% End initialization code - DO NOT EDIT

% --- Executes just before GUI_Taylor_Maccoll is made visible.
function GUI_Taylor_Maccoll_OpeningFcn(hObject, eventdata, handles, varargin)
handles.output = hObject;
guidata(hObject, handles);

% --- Outputs from this function are returned to the command line.
function varargout = GUI_Taylor_Maccoll_OutputFcn(hObject, eventdata, handles) 
varargout{1} = handles.output;

% INITIAL VARIABLE DEFINITIONS
theta_s_d = 15;                                                             % Shock angle [deg]
theta_s_r = theta_s_d*(pi/180);                                             % Shock angle [rad]
theta_c_d = 0;                                                              % Cone angle [deg]
theta_c_r = theta_c_d*(pi/180);                                             % Cone angle [rad]
M1        = 5;                                                              % Freestream Mach number []
gam       = 1.4;                                                            % Ratio of specific heats []
maxIter   = 200;                                                            % Maximum simulation iterations []
errorTol  = 0.04;                                                           % Convergence error tolerance
numLevs   = 100;                                                            % Number of contour levels for plotting

% Assign variables into the base workspace
assignin('base','theta_s_d',theta_s_d);
assignin('base','theta_s_r',theta_s_r);
assignin('base','theta_c_d',theta_c_d);
assignin('base','theta_c_r',theta_c_r);
assignin('base','M1',M1);
assignin('base','gam',gam);
assignin('base','maxIter',maxIter);
assignin('base','errorTol',errorTol);
assignin('base','numLevs',numLevs);

% Initial enabling/disabling of fields
set(handles.editConeAngle,'Enable','off');                                  % Disable cone angle input field
set(handles.editMaxIters,'Enable','off');                                   % Disable maximum iterations input field
set(handles.editErrorTol,'Enable','off');                                   % Disable error tolerance input field

% ----------------------------------------------------------------------- %
% ----------------------------------------------------------------------- %
% --------------------------- INITIALIZATION ---------------------------- %
% ----------------------------------------------------------------------- %
% ----------------------------------------------------------------------- %

% POP ----------------------- Simulation Type -----------------------------
function popSimType_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ------------------------- Shock Angle ------------------------------
function editShockAngle_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ------------------------- Cone Angle -------------------------------
function editConeAngle_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ------------------------- Mach Number ------------------------------
function editMachNumber_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ------------------ Ratio of Specific Heats -------------------------
function editGamma_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ---------------------- Maximum Iterations --------------------------
function editMaxIters_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ---------------------- Error Tolerance -----------------------------
function editErrorTol_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT --------------------- Contour Levels -------------------------------
function editLevels_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ---------------------- Solution: Iteration -------------------------
function editSolIteration_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT --------------------- Solution: Shock Angle ------------------------
function editSolShockAngle_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ---------------------- Solution: Cone Angle ------------------------
function editSolConeAngle_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT ---------------------- Solution: Mach Number -----------------------
function editSolMachNumber_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% EDIT -------------- Solution: Cone Surface Mach Number ------------------
function editSolConeMachNumber_CreateFcn(hObject, eventdata, handles)
if ispc && isequal(get(hObject,'BackgroundColor'), get(0,'defaultUicontrolBackgroundColor'))
    set(hObject,'BackgroundColor','white');
end

% ----------------------------------------------------------------------- %
% ----------------------------------------------------------------------- %
% ----------------------------- CALLBACKS ------------------------------- %
% ----------------------------------------------------------------------- %
% ----------------------------------------------------------------------- %

% POP ----------------------- Simulation Type -----------------------------
function popSimType_Callback(hObject, eventdata, handles)
popSelection = get(hObject,'Value');
if (popSelection == 1)
    % Enable/disable appropriate fields
    set(handles.editShockAngle,'Enable','on');
    set(handles.editConeAngle,'Enable','off');
    set(handles.editMachNumber,'Enable','on');
    set(handles.editMaxIters,'Enable','off');
    set(handles.editErrorTol,'Enable','off');
    
    % Update fields to something that will actually work
    theta_s_d = 15;                                                         % Shock angle [deg]
    theta_s_r = theta_s_d*(pi/180);                                         % Convert shock angle to radians
    theta_c_d = 0;                                                          % Cone angle [deg]
    theta_c_r = theta_c_d*(pi/180);                                         % Convert cone angle to radians
    set(handles.editShockAngle,'String',num2str(theta_s_d));                % Set the edit text box
    set(handles.editConeAngle,'String',num2str(theta_c_d));                 % Set the edit text box
    assignin('base','theta_s_d',theta_s_d);
    assignin('base','theta_s_r',theta_s_r);
    assignin('base','theta_c_d',theta_c_d);
    assignin('base','theta_c_r',theta_c_r);
elseif (popSelection == 2)
    % Enable/disable appropriate fields
    set(handles.editShockAngle,'Enable','on');
    set(handles.editConeAngle,'Enable','on');
    set(handles.editMachNumber,'Enable','off');
    set(handles.editMaxIters,'Enable','on');
    set(handles.editErrorTol,'Enable','on');
    
    % Update fields to something that will actually work
    theta_s_d = 38.66;                                                      % Shock angle [deg]
    theta_s_r = theta_s_d*(pi/180);                                         % Convert shock angle to radians
    theta_c_d = 8.7;                                                        % Cone angle [deg]
    theta_c_r = theta_c_d*(pi/180);                                         % Convert the cone angle to radians
    set(handles.editShockAngle,'String',num2str(theta_s_d));                % Set the edit text box
    set(handles.editConeAngle,'String',num2str(theta_c_d));                 % Set the edit text box
    assignin('base','theta_s_d',theta_s_d);
    assignin('base','theta_s_r',theta_s_r);
    assignin('base','theta_c_d',theta_c_d);
    assignin('base','theta_c_r',theta_c_r);
end

% EDIT ------------------------ Shock Angle -------------------------------
function editShockAngle_Callback(hObject, eventdata, handles)
theta_s_d = str2double(get(hObject,'String'));                              % Read in shock angle in degrees
theta_s_r = theta_s_d*(pi/180);                                             % Convert shock angle to radians
assignin('base','theta_s_d',theta_s_d);
assignin('base','theta_s_r',theta_s_r);

% EDIT ------------------------- Cone Angle -------------------------------
function editConeAngle_Callback(hObject, eventdata, handles)
theta_c_d = str2double(get(hObject,'String'));                              % Read in cone angle in degrees
theta_c_r = theta_c_d*(pi/180);                                             % Convert cone angle to radians
assignin('base','theta_c_d',theta_c_d);
assignin('base','theta_c_r',theta_c_r);

% EDIT ------------------------- Mach Number ------------------------------
function editMachNumber_Callback(hObject, eventdata, handles)
M1 = str2double(get(hObject,'String'));                                     % Read in freestream Mach number
assignin('base','M1',M1);

% EDIT ------------------ Ratio of Specific Heats -------------------------
function editGamma_Callback(hObject, eventdata, handles)
gam = str2double(get(hObject,'String'));                                    % Read in specific heat ratio
assignin('base','gam',gam);

% EDIT ---------------------- Maximum Iterations --------------------------
function editMaxIters_Callback(hObject, eventdata, handles)
maxIter = str2double(get(hObject,'String'));                                % Read in maximum number of simulation iterations
assignin('base','maxIter',maxIter);

% EDIT ---------------------- Error Tolerance -----------------------------
function editErrorTol_Callback(hObject, eventdata, handles)
errorTol = str2double(get(hObject,'String'));                               % Read in simulation convergence error tolerance
assignin('base','errorTol',errorTol);

% EDIT --------------------- Contour Levels -------------------------------
function editLevels_Callback(hObject, eventdata, handles)
numLevs = str2double(get(hObject,'String'));                                % Number of contour levels for plotting
assignin('base','numLevs',numLevs);

% EDIT ---------------------- Solution: Iteration -------------------------
function editSolIteration_Callback(hObject, eventdata, handles)
% Nothing is set in this callback

% EDIT ---------------------- Solution: Mach Number -----------------------
function editSolMachNumber_Callback(hObject, eventdata, handles)
% Nothing is set in this callback

% EDIT --------------------- Solution: Shock Angle ------------------------
function editSolShockAngle_Callback(hObject, eventdata, handles)
% Nothing is set in this callback

% EDIT ---------------------- Solution: Cone Angle ------------------------
function editSolConeAngle_Callback(hObject, eventdata, handles)
% Nothing is set in this callback

% EDIT -------------- Solution: Cone Surface Mach Number ------------------
function editSolConeMachNumber_Callback(hObject, eventdata, handles)
% Nothing is set in this callback

% PUSH ------------------------ S O L V E ---------------------------------
function pushSolve_Callback(hObject, eventdata, handles)
% =========================================================================
% - Solve two different cases, depending on user input
%   1) Known shock angle and Mach number
%   2) Known shock angle and cone angle
% =========================================================================

% Get the simulation type requested by user
simType = get(handles.popSimType,'Value');

% KNOWNS: Shock Angle, Mach Number
if (simType == 1)
    % Set the solutions panel outline to red while solving
    set(handles.panelSolutions,'ShadowColor','r');
    drawnow();
    
    % Evalin the relevant variables
    theta_s_r = evalin('base','theta_s_r');                                 % Shock angle [rad]
    theta_s_d = evalin('base','theta_s_d');                                 % Shock angle [deg]
    M1        = evalin('base','M1');                                        % Freestream Mach number []
    gam       = evalin('base','gam');                                       % Specific heat ratio []
    
    % Solve for cone angle (deflection angle)
    % - Known the Mach number and shock angle, so solve for cone angle
    [theta_c_r] = THETA_BETA_M_v2(0,theta_s_r,M1,gam,'rad');                % Cone angle [rad]
    
    % Mach number behind oblique shock
    % - Use oblique shock relations to get M behind shock
    Mn1 = M1*sin(theta_s_r);                                                % Normal Mach number pre-shock, Eqn. 4.7 (pg. 135)
    N   = 1 + ((gam-1)/2)*Mn1^2;                                            % Numerator, Eqn. 3.51 numerator (pg. 89)
    D   = (gam*Mn1^2) - ((gam-1)/2);                                        % Denominator, Eqn. 3.51 denominator (pg. 89)
    Mn2 = sqrt(N/D);                                                        % Normal Mach number post-shock, Eqn. 3.51 (pg. 89)
    M2  = Mn2/(sin(theta_s_r-theta_c_r));                                   % Post-shock Mach number, Eqn. 4.12 (pg. 135)
    
    % Initial conditions for ODE solver
    V      = ((2/((gam-1)*M2^2))+1)^(-1/2);                                 % Total velocity
    Vtheta = -V*(sin(theta_s_r-theta_c_r));                                 % Angular velocity
    Vr     = V*(cos(theta_s_r-theta_c_r));                                  % Radial velocity
    
    % Theta range and initial conditions of Vr and Vr'
    thetaSpan = [theta_s_r; 1e-10];                                         % Integrate from shock angle to ~ 0 degrees
    V_init    = [Vr; Vtheta];                                               % Initial values for Vr and dVr/dTheta (Vtheta)
    
    % Solve the state-space ODE (stiff solver)
    % - Solving an initial value problem
    % - options = odeset('name1',value1,'name2',value2,...)
    % - EVENTS helps locate important transitions through zeros of user-
    %     defined functions
    % - This particular event stops the sim when we reach the cone wall
    % - RelTol: measure of the error relative to the size of each solution
    %     component
    options = odeset('Events',@EVENTS,'RelTol',1e-5);                       % Set options for event handling and tolerances
    [sol]   = ode15s(@TM_EQUATIONS,thetaSpan,V_init,options,gam);           % Solve the ODE using a stiff solver
    
    % If ODE solver worked, calculate angle and Mach number at the cone
    [n,m]  = size(sol.y);                                                   % Get the size of the solution array
    if (n > 0 && m > 0 && isempty(sol.ie) ~= 1)                             % If the solution converged
        theta_c_r = sol.xe;                                                 % Final cone angle [rad]
        theta_c_d = theta_c_r.*(180/pi);                                    % Final cone angle [deg]
        Vc2       = sol.ye(1)^2 + sol.ye(2)^2;                              % Total velocity squared []
        Mc        = ((1.0/Vc2-1)*(gam-1)/2)^-0.5;                           % Mach number at cone surface
        
        % Print solutions in the GUI
        set(handles.editSolIteration,'String','-');
        set(handles.editSolShockAngle,'String',num2str(theta_s_d));
        set(handles.editSolConeAngle,'String',num2str(theta_c_d));
        set(handles.editSolMachNumber,'String',num2str(M1));
        set(handles.editSolConeMachNumber,'String',num2str(Mc));
    else
        % Indicate in the command window that no solution was found
        fprintf('No cone angle solution found!\n');
    end
    
    % Solution arrays for shock layer
    sol_V2    = (sol.y(1,:).^2 + sol.y(2,:).^2)';                           % Total velocity squared
    sol_Mc    = ((1./sol_V2-1).*(gam-1)/2).^(-0.5);                         % Cone surface Mach number
    sol_X_rad = sol.x';                                                     % Integration angles [rad]
    sol_X_deg = (sol.x').*(180/pi);                                         % Integration angles [deg]
    
    % Call plotting function
    PLOTTING(handles,sol_X_rad,sol_Mc,M1,theta_c_r);                        % Plot the Mach number contours along with cone
    
    % Set the solutions panel outline to blue when done solving
    set(handles.panelSolutions,'ShadowColor','b');
    drawnow();
    
% KNOWNS: Shock Angle, Cone Angle
elseif (simType == 2)
    % Set the solutions panel outline to red while solving
    set(handles.panelSolutions,'ShadowColor','k');
    drawnow();
    
    % Evalin the relevant variables
    theta_s_r = evalin('base','theta_s_r');                                 % Shock angle [rad]
    theta_s_d = evalin('base','theta_s_d');                                 % Shock angle [deg]
    theta_c_r = evalin('base','theta_c_r');                                 % Cone angle [rad]
    theta_c_d = evalin('base','theta_c_d');                                 % Cone angle [deg]
    gam       = evalin('base','gam');                                       % Ratio of specific heats []
    maxIter   = evalin('base','maxIter');                                   % Maximum iterations [#]
    errorTol  = evalin('base','errorTol');                                  % Error tolerance [#]
    
    % Freestream Mach number
    % - Compute initial guess M from shock and cone angles
    [M1] = THETA_BETA_M_v2(theta_c_r,theta_s_r,0,gam,'rad');                % Freestream Mach number []
    
    % Loop through until cone angles converge
    for i = 1:1:maxIter
        set(handles.editSolIteration,'String',num2str(i));                  % Show iteration number in GUI
        set(handles.editSolIteration,'ForegroundColor','r');                % Make iteration number red so we know we're currently solving
        drawnow();                                                          % Make sure it updates in real-time
        
        % Freestream Mach number
        [theta_c_r] = THETA_BETA_M(0,theta_s_r,M1,gam);
        
        % Mach number behind oblique shock
        Mn1 = M1*sin(theta_s_r);                                            % Normal Mach number pre-shock, Eqn. 4.7 (pg. 135)
        N   = 1 + ((gam-1)/2)*Mn1^2;                                        % Numerator, Eqn. 3.51 numerator (pg. 89)
        D   = (gam*Mn1^2) - ((gam-1)/2);                                    % Denominator, Eqn. 3.51 denominator (pg. 89)
        Mn2 = sqrt(N/D);                                                    % Normal Mach number post-shock, Eqn. 3.51 (pg. 89)
        M2  = Mn2/(sin(theta_s_r-theta_c_r));                               % Post-shock Mach number, Eqn. 4.12 (pg. 135)
        
        % Calculate initial velocities
        V      = ((2/((gam-1)*M2^2))+1)^(-1/2);                             % Full velocity []
        Vtheta = -V*(sin(theta_s_r-theta_c_r));                             % Angular velocity []
        Vr     = V*(cos(theta_s_r-theta_c_r));                              % Radial velocity []
        
        % Theta range and initial conditions of Vr and Vr'
        thetaSpan = [theta_s_r; 1e-10];                                     % Integrate from shock angle to ~ 0 degrees
        V_init    = [Vr; Vtheta];                                           % Initial values for Vr and dVr/dTheta (Vtheta)
        
        % Solve the state-space ODE (stiff solver)
        options = odeset('Events',@EVENTS,'RelTol',1e-5);                   % Set options for event handling and tolerances
        [sol]   = ode15s(@TM_EQUATIONS,thetaSpan,V_init,options,gam);       % Solve the ODE using a stiff solver
        
        % Calculate the angle and Mach number at the cone
        [n,m]  = size(sol.y);                                               % Get the size of the solution array
        if (n > 0 && m > 0 && isempty(sol.ie) ~= 1)                         % If the solution converged
            theta_c_r_sol = sol.xe;                                         % Final cone angle [rad]
            theta_c_d_sol = theta_c_r_sol*(180/pi);                         % Final cone angle [deg]
            Vc2           = sol.ye(1)^2 + sol.ye(2)^2;                      % Total velocity squared []
            Mc            = ((1.0/Vc2-1)*(gam-1)/2)^-0.5;                   % Mach number at cone surface []
            
            % Check whether cone angle calculated from FS M1 matches the input
            if (abs(theta_c_d_sol-theta_c_d) <= errorTol)
                set(handles.editSolIteration,'ForegroundColor','w');
                break;
            else
                adjFac = 0.005*sign(theta_c_d-theta_c_d_sol);               % Adjustment factor, includes sign
                M1 = M1 + adjFac*M1;                                        % Increase/decrease M1 based on cone angles
            end
        else                                                                % No solution was found after all iterations
            fprintf('No cone angle solution\n');                            % Indicate no solution was found in command window
            set(handles.editSolIteration,'ForegroundColor','r');            % Set itertion color to red
            return;
        end
    end
    
    % Solution arrays for shock layer
    sol_V2    = (sol.y(1,:).^2 + sol.y(2,:).^2)';                           % Total velocity squared
    sol_Mc    = ((1./sol_V2-1).*(gam-1)/2).^(-0.5);                         % Cone surface Mach number
    sol_X_rad = sol.x';                                                     % Integration angles [rad]
    assignin('base','sol_Mc',sol_Mc);                                       % Bring the cone Mach number into base workspace
    
    % Print solutions in the GUI
    set(handles.editSolShockAngle,'String',num2str(theta_s_d));
    set(handles.editSolConeAngle,'String',num2str(theta_c_d_sol));
    set(handles.editSolMachNumber,'String',num2str(M1));
    set(handles.editSolConeMachNumber,'String',num2str(Mc));
    
    % Call the plotting function
    PLOTTING(handles,sol_X_rad,sol_Mc,M1,theta_c_r_sol);                    % Plot the Mach number contours
    
    % Set the solutions panel outline to blue when done solving
    set(handles.panelSolutions,'ShadowColor','b');
    drawnow();
    
end

% FUNCTION -------------------- Plotting ----------------------------------
function [] = PLOTTING(handles,sol_X_rad,sol_Mc,M1,theta_c_r)
% =========================================================================
%  - Does not return anything
% =========================================================================

% Plot top half with freestream solution
dAng     = (pi-sol_X_rad(1))/8;                                             % Freestream angle step size [rad]
angArray = (pi:-dAng:sol_X_rad(1)+dAng)';                                   % Freestream angle array [rad]
[r,t]    = meshgrid(0:0.1:2,[angArray; sol_X_rad]);                         % Polar coordinate meshgrid
                                                                            % Includes integration angles now
% Extract freestream Mach numbers too
[row,col] = size(r);                                                        % Size of the meshgrid matrix
for i = 1:1:row                                                             % Loop through all rows
    for j = 1:1:col                                                         % Loop through all columns
        if (t(i,j) > sol_X_rad(1))                                          % If we are in the freestream
            z1(i,j) = M1;                                                   % Set the Mach number to the input freestream M
        end
    end
end
z2 = repmat(sol_Mc',col,1)';                                                % Make a matrix of the solution Mach numbers
z  = [z1; z2];                                                              % Concatenate the freestream and solution Mach number matrices

% Convert from polar to Cartesian coordinates
[x,y] = pol2cart(t,r);                                                      % Convert from 'r' and 't' to 'x' and 'y'

% Get limits for plotting bounds
numAngs = length(sol_X_rad);                                                % Number of actual solution angles
xMax    = max(x(end-numAngs,:));                                            % Maximum x location of only shock layer solutions (no FS)
yMax    = max(y(end-numAngs,:));                                            % Maximum y location of only shock layer solutions (no FS)

% Number of contour levels
numLevs = evalin('base','numLevs');                                         % Number of contour levels (more = smoother contours)
zmin    = min(min(z2));                                                     % Minimum Mach number of only shock layer solutions (no FS)
zmax    = max(max(z2));                                                     % Maximum Mach number of only shock layer solutions (no FS)
zinc    = (zmax-zmin)/numLevs;                                              % Increment for the levels array
zlevs   = zmin:zinc:zmax;                                                   % Specify the contour level values

% Plot the data
axes(handles.plotData);
cla; hold on;                                                               % Clear the axes; allows multiple plots
[~,hTop] = contourf(x,y,z,zlevs);                                           % Plot the upper contours for FS and shock layer solutions
[~,hBot] = contourf(x,-y,z,zlevs);                                          % Plot the lower contours for FS and shock layer solutions
set(hTop,'EdgeColor','none');                                               % Hide the black lines between contours for upper contours
set(hBot,'EdgeColor','none');                                               % Hide the black lines between contours for lower contours
axis('auto');                                                               % Set axes to auto scale
if (xMax > 0)
    xlim([0 xMax]);                                                         % Set the X axis limits
end
ylim([-yMax yMax]);                                                         % Set the Y axis limits

% Plot the triangle wedge
if (xMax == 0)
    rMax = max(max(r));
    xW = [0 rMax rMax 0];                                                   % Define X coordinates for the cone
else
    xW = [0 xMax xMax 0];
end
yW = [0 xW(2)*tan(theta_c_r(end)) -xW(3)*tan(theta_c_r(end)) 0];            % Define Y coordinates for the cone
fill(xW,yW,'k');                                                            % Plot the cone in the figure (black)

% Label the axes
xlabel('X Coordinate');
ylabel('Y Coordinate');

% PUSH ----------------------- Exit the GUI -------------------------------
function pushExit_Callback(hObject, eventdata, handles)
clc;                                                                        % Clear the command window
evalin('base','clear all');                                                 % Clear all variables
delete(handles.figureGUITM);                                                % Delete the GUI figure window
