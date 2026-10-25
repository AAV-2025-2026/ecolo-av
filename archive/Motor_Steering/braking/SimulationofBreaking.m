%% AAV Longitudinal Closed-Loop Simulation
%  - Outer-loop speed PID (navigation reference -> speed control)
%  - Throttle command for the drive motor
%  - Brake command with INNER brake PID (all signals normalized 0..1)
%  - Simple longitudinal vehicle dynamics
%
%  This version uses ONLY normalized commands for throttle and brake:
%      throttle_cmd, brake_cmd, brake_force ∈ [0, 1]
%  Hardware-specific scaling (ADC counts, DAC values, etc.) will be done
%  later in firmware as a separate mapping layer.

clear; clc; close all;

%% ------------------------------------------------------------------------
% Simulation settings
% -------------------------------------------------------------------------
Ts   = 0.01;          % Sampling period [s] (10 ms)
Tend = 20;            % Total simulation time [s]
t    = 0:Ts:Tend;     % Time vector
N    = numel(t);      % Number of simulation steps

%% ------------------------------------------------------------------------
% Reference speed
% -------------------------------------------------------------------------
v_ref = zeros(1, N);

for k = 1:N
    if t(k) < 5
        % 0–5 s: ramp 0 -> 1 m/s
        v_ref(k) = 0.2 * t(k);
    elseif t(k) < 10
        % 5–10 s: cruise at 1 m/s
        v_ref(k) = 1.0;
    elseif t(k) < 15
        % 10–15 s: ramp 1 -> 0 m/s
        v_ref(k) = 1.0 - 0.2 * (t(k) - 10);
    else
        % 15–20 s: standstill
        v_ref(k) = 0.0;
    end
end

%% ------------------------------------------------------------------------
% Vehicle physical parameters
% -------------------------------------------------------------------------
m       = 60;     % Mass [kg] (cart + payload)
C_drag  = 3;      % Linear drag coefficient (rolling + air)

% Throttle mapping: throttle_cmd = 1.0 -> K_throt Newtons of drive force
K_throt = 40;     % Max drive force [N] (tunable)

% Brake mapping: brake_force = 1.0 -> K_brake_force Newtons of brake force
K_brake_force = 80;  % Max brake force [N] (tunable)

%% ------------------------------------------------------------------------
% Outer-loop speed PID controller
% -------------------------------------------------------------------------
Kp_v = 40;    % Proportional gain
Ki_v = 5;     % Integral gain
Kd_v = 0.0;   % Derivative gain

int_e_v  = 0;     % Speed integrator state
prev_e_v = 0;     % Previous speed error
u_max    = 80;    % Saturation on |u_speed| [N] (used for mapping)

%% ------------------------------------------------------------------------
% Inner-loop brake PID
% -------------------------------------------------------------------------
% Initial guess for normalized brake PID
P_b  = 5.0;      % Proportional gain on normalized error
I_b  = 3.0;      % Integral gain
D_b  = 0.1;      % Derivative gain

% Limits and deadzone in normalized units
positionDeadzone_b = 0.01;   % Small deadzone (1% of full range)
errorLimit_b       = 1.0;    % Max absolute error (full range)
integralLimit_b    = 0.5;    % Limit on integral state
maxPower_b         = 1.0;    % PID output saturation (0..1 magnitude)

% PID state for brake loop
intval_b   = 0;      % Integral term state
prev_err_b = 0;      % Previous brake error

% Brake actuator first-order dynamics:
%   d(brake_force)/dt = (-brake_force + K_b_act * u_b) / tau_b
% where u_b is the saturated PID output in [0..1].
tau_b   = 0.15;      % Time constant [s]
K_b_act = 1.0;       % Actuator gain

%% ------------------------------------------------------------------------
% State variables
% -------------------------------------------------------------------------
v            = zeros(1, N);  % True speed [m/s]
v_meas       = zeros(1, N);  % Measured speed [m/s]
throttle_cmd = zeros(1, N);  % Throttle command [0..1]
brake_cmd    = zeros(1, N);  % Desired brake level [0..1]
brake_force  = zeros(1, N);  % Actual brake level [0..1]

%% ------------------------------------------------------------------------
% Main simulation loop
% -------------------------------------------------------------------------
for k = 2:N

    %% Sensor measurement
    v_meas(k-1) = v(k-1);

    %% Outer-loop speed PID
    e_v  = v_ref(k-1) - v_meas(k-1);
    int_e_v = int_e_v + e_v * Ts;
    der_e_v = (e_v - prev_e_v) / Ts;
    prev_e_v = e_v;

    u_speed = Kp_v * e_v + Ki_v * int_e_v + Kd_v * der_e_v;
    u_speed = max(min(u_speed, u_max), -u_max);

    %% Decide throttle or brake
    if u_speed >= 0
        throttle_cmd(k) = u_speed / u_max;   % 0..1
        brake_cmd(k)    = 0.0;
    else
        throttle_cmd(k) = 0.0;
        brake_cmd(k)    = -u_speed / u_max;  % 0..1
    end

    %% Throttle actuator -> drive force
    F_drive = K_throt * throttle_cmd(k);

    %% Inner brake PID: brake_cmd -> brake_force
    % Current and desired normalized brake levels
    brakePos = brake_force(k-1);   % "measured" brake level
    setpoint = brake_cmd(k);       % desired brake level

    % Error definition (same sign convention as C++: brakePos - setpoint)
    err_b = setpoint - brakePos;;

    % Deadzone in normalized units
    if abs(err_b) < positionDeadzone_b
        err_b = 0;
    end

    % Error saturation
    err_b = max(min(err_b,  errorLimit_b), -errorLimit_b);

    % Integral term (only when error is not zero)
    if err_b ~= 0
        intval_b = intval_b + err_b * Ts;
        intval_b = max(min(intval_b, integralLimit_b), -integralLimit_b);
    else
        intval_b = 0;
    end

    % Derivative term
    derr_b     = (err_b - prev_err_b) / Ts;
    prev_err_b = err_b;

    % PID output (still in normalized scale)
    prop_b = P_b * err_b;
    int_b  = I_b * intval_b;
    der_b  = D_b * derr_b;

    u_b = prop_b + int_b + der_b;

    % Saturate PID output to [-maxPower_b, maxPower_b]
    u_b = max(min(u_b, maxPower_b), -maxPower_b);

    % For actuator dynamics we only need a non-negative level.
    % Negative u_b means "release brake"; we can model this simply
    % through the first-order dynamics toward 0.
    % Take u_act as magnitude in [0..1].
    u_act = max(u_b, 0);   % clamp to [0, 1]

    % First-order actuator dynamics on brake_force
    brake_force(k) = brake_force(k-1) + Ts * ...
        ( (-brake_force(k-1) + K_b_act * u_act) / tau_b );

    % Limit brake_force to [0, 1]
    brake_force(k) = max(min(brake_force(k), 1.0), 0.0);

    % Physical brake force
    F_brake = K_brake_force * brake_force(k);

    %% Vehicle longitudinal dynamics
    F_drag = C_drag * v(k-1);
    a      = (F_drive - F_brake - F_drag) / m;

    v(k)   = v(k-1) + Ts * a;
    if v(k) < 0
        v(k) = 0;
    end
end

v_meas(end) = v(end);


%% ------------------------------------------------------------------------
% Plot results
% -------------------------------------------------------------------------
figure;

% Speed tracking
subplot(3,1,1);
plot(t, v_ref, '--', 'LineWidth', 1.2); hold on;
plot(t, v, 'LineWidth', 1.5);
xlabel('Time [s]');
ylabel('Speed [m/s]');
legend('v_{ref}', 'v', 'Location', 'Best');
title('Closed-loop speed tracking');
grid on;

% Outer-loop commands
subplot(3,1,2);
plot(t, throttle_cmd, 'LineWidth', 1.5); hold on;
plot(t, brake_cmd, 'LineWidth', 1.5);
ylabel('Command');
legend('throttle\_cmd', 'brake\_cmd', 'Location', 'Best');
title('Outer-loop commands');
grid on;

% Inner brake PID output
subplot(3,1,3);
plot(t, brake_force, 'LineWidth', 1.5);
xlabel('Time [s]');
ylabel('Brake force (0–1)');
title('Inner brake PID output');
grid on;
